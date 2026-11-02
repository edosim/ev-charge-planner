"""Test for models used on backend"""

import pytest

from pydantic import ValidationError


from main import Intensity, Slot, ForecastResponse

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
