"""Test for fetch_forecast, using a fake HTTP client

using httpx.MockTransport"""

import pytest


import asyncio
import httpx
from datetime import datetime, timezone
from pydantic import ValidationError

from main import (Intensity,
                  Slot,
                  ForecastResponse,
                  fetch_forecast,
)
                  

# ---- test validation of Intensity ------

@pytest.mark.parametrize("data, expected",[
    ({"forecast": 100, "actual": 150, "index": "moderate"},
     {"forecast": 100, "actual": 150, "index": "moderate"}),     #both numbers
    ({"forecast": None, "actual": 150, "index": "moderate"},
     {"forecast": None, "actual": 150, "index": "moderate"}),    #Forecast is None
    ({"forecast": 100, "actual": None, "index": "moderate"},
     {"forecast": 100, "actual": None, "index": "moderate"}),    #Actual is None
    ({"forecast": 100, "index": "moderate"},
     {"forecast": 100, "actual": None, "index": "moderate"}),    #Actual defaults to None
])
def test_intensity_accepts_valid_forecast_and_actual_formats(data,expected):
    intensity = Intensity.model_validate(data)
    assert intensity.forecast == expected['forecast']
    assert intensity.actual == expected['actual']
    assert intensity.index == expected['index']

@pytest.mark.parametrize("index",["very low", "low", "moderate", "high", "very high"])
def test_all_api_index_values_are_accepted(index):
    intensity = Intensity.model_validate({"forecast": 100, "actual": 150, "index": index})
    assert intensity.index == index


def test_forecast_is_required():
    with pytest.raises(ValidationError):
        Intensity.model_validate({"index": "moderate"})

@pytest.mark.parametrize("bad_data",[
    {"actual": 150, "index": "moderate"},                     #no forecast value
    {"forecast": -1, "actual": 150, "index": "moderate"},     #negative forecast value
    {"forecast": 100, "actual": 150, "index": "medium"},      #incorrect index string
    {"forecast": 100, "actual": 150, "index": "Moderate"},    #incorrect capitalisation
])
def test_intensity_rejects_invalid_data(bad_data):
    with pytest.raises(ValidationError):
        Intensity.model_validate(bad_data)

# ---- test validation of Slot ------

INTENSITY = {"forecast": 120, "actual": None, "index": "moderate"}

def test_slot_accepts_api_format():
    slot = Slot.model_validate({"from": "2026-10-28T12:00Z", "to": "2026-10-28T12:30Z", "intensity": INTENSITY})
    assert slot.start.tzinfo is not None

def test_slot_converts_to_utc():
    slot = Slot.model_validate({"from": "2026-10-28T13:00+01:00", "to": "2026-10-28T13:30+01:00", "intensity": INTENSITY})
    assert slot.start.hour == 12
    assert slot.start.utcoffset().total_seconds() == 0

def test_slot_rejects_time_without_timezone():
    with pytest.raises(ValidationError):
        Slot.model_validate({"from": "2026-10-28T12:00", "to": "2026-10-28T12:30", "intensity": INTENSITY})

def test_slot_rejects_wrong_slot_length():
    with pytest.raises(ValidationError):
        Slot.model_validate({"from": "2026-10-28T12:00Z", "to": "2026-10-28T13:00Z", "intensity": INTENSITY})

def test_slot_rejects_wrong_slot_length():
    with pytest.raises(ValidationError):
        Slot.model_validate({"from": "2026-10-28T12:00Z", "to": "2026-10-28T13:00Z", "intensity": INTENSITY})

# ---- test validation of ForecastResponse ------

DATA = [
    {"from": "2026-10-27T12:00Z", "to": "2026-10-27T12:30Z", "intensity": INTENSITY},
    {"from": "2026-10-27T12:30Z", "to": "2026-10-27T13:00Z", "intensity": INTENSITY},
    {"from": "2026-10-27T13:00Z", "to": "2026-10-27T13:30Z", "intensity": INTENSITY},
    #half-hour gap
    {"from": "2026-10-27T14:00Z", "to": "2026-10-27T14:30Z", "intensity": INTENSITY}, 
]

def forecast_response_accepts_api_format():
    ForecastResponse.model_validate(DATA[:3])
    assert len(ForecastResponse) == len(3)

def forecast_response_rejects_gap():
    with pytest.raises(ValidationError):
        ForecastResponse.model_validate(DATA)

# ----------

TEST_RESPONSE = {
    'data': [
        {"from": "2026-10-27T12:00Z", "to": "2026-10-27T12:30Z",
         "intensity": {"forecast": 50, "actual": None, "index": "moderate"}},
        {"from": "2026-10-27T12:30Z", "to": "2026-10-27T13:00Z",
         "intensity": {"forecast": 100, "actual": None, "index": "low"}},
        {"from": "2026-10-27T13:00Z", "to": "2026-10-27T13:30Z",
         "intensity": {"forecast": None, "actual": None, "index": "moderate"}},
        {"from": "2026-10-27T13:30Z", "to": "2026-10-27T14:00Z",
         "intensity": {"forecast": 100, "actual": None, "index": "low"}},
    ]
}

def fetch_with(handler):
    """Run fetch with a fake server"""
    async def run():
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            return await fetch_forecast(client)
    return asyncio.run(run())



def test_parses_response_and_excludes_all_after_missing_forecasts():
    slots = fetch_with(lambda request: httpx.Response(200, json=TEST_RESPONSE))

    assert len(slots) == 2
    assert [s.intensity.forecast for s in slots] == [50, 100]
    assert slots[0].start == datetime(2026, 10, 27, 12, 0, tzinfo=timezone.utc)
    assert slots[0].end == datetime(2026, 10, 27, 12, 30, tzinfo=timezone.utc)
    assert slots[1].intensity.index == "low"

def test_calls_the_48h_forecast_endpoint():
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json={"data": []})

    fetch_with(handler)

    assert len(seen) == 1
    path = seen[0].url.path
    assert path.startswith("/intensity/")
    assert path.endswith("/fw48h")

def test_server_error_raises():
    with pytest.raises(httpx.HTTPStatusError):
        fetch_with(lambda request: httpx.Response(500))


def test_unexpected_shape_raises():
    from pydantic import ValidationError

    broken = {"data": [{"to": "2026-10-27T12:00Z"}]}       # missing "from" and "intensity"
    with pytest.raises(ValidationError):
        fetch_with(lambda request: httpx.Response(200, json=broken))
