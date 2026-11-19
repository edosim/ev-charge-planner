"""Test for models used on backend"""

import pytest

from pydantic import ValidationError
from datetime import timezone
from schemas import Intensity, Slot, ForecastResponse, ChargeRequest
from constants import (
    MAX_CHARGE_KWH, MIN_CHARGE_KWH,
    MAX_CHARGE_RATE_KW, MIN_CHARGE_RATE_KW,
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
    assert intensity.forecast == expected["forecast"]
    assert intensity.actual == expected["actual"]
    assert intensity.index == expected["index"]

@pytest.mark.parametrize("index",["very low", "low", "moderate", "high", "very high", None, "medium"])
def test_any_api_index_values_is_accepted(index):
    intensity = Intensity.model_validate({"forecast": 100, "actual": 150, "index": index})
    assert intensity.index == index

def test_forecast_is_required():
    with pytest.raises(ValidationError):
        Intensity.model_validate({"index": "moderate"})

def test_forecast_cannot_be_negative():
    with pytest.raises(ValidationError):
        Intensity.model_validate({"forecast": -1, "actual": 150, "index": "moderate"})

# ---- test validation of Slot ------

INTENSITY = {"forecast": 120, "actual": None, "index": "moderate"}

def test_slot_accepts_api_format():
    slot = Slot.model_validate({"from": "2026-10-28T12:00Z", "to": "2026-10-28T12:30Z", "intensity": INTENSITY})
    assert slot.start.tzinfo is not None

def test_slot_converts_to_utc():
    slot = Slot.model_validate({"from": "2026-10-28T13:00+01:00", "to": "2026-10-28T13:30+01:00", "intensity": INTENSITY})
    assert slot.start.hour == 12
    assert slot.start.tzinfo == timezone.utc

def test_slot_rejects_time_without_timezone():
    with pytest.raises(ValidationError):
        Slot.model_validate({"from": "2026-10-28T12:00", "to": "2026-10-28T12:30", "intensity": INTENSITY})

def test_slot_rejects_wrong_slot_length():
    with pytest.raises(ValidationError):
        Slot.model_validate({"from": "2026-10-28T12:00Z", "to": "2026-10-28T13:00Z", "intensity": INTENSITY})

def test_slot_is_frozen():
    slot = Slot.model_validate({"from": "2026-10-28T12:00Z", "to": "2026-10-28T12:30Z", "intensity": INTENSITY})
    with pytest.raises(ValidationError):
        slot.intensity = Intensity.model_validate(INTENSITY | {"index": "low"}) # type: ignore[misc]

def test_intensity_withing_slot_is_frozen():
    slot = Slot.model_validate({"from": "2026-10-28T12:00Z", "to": "2026-10-28T12:30Z", "intensity": INTENSITY})
    with pytest.raises(ValidationError):
        slot.intensity.forecast = 20 # type: ignore[misc]

# ---- test validation of ForecastResponse ------

DATA = [
    {"from": "2026-10-27T12:00Z", "to": "2026-10-27T12:30Z", "intensity": INTENSITY},
    {"from": "2026-10-27T12:30Z", "to": "2026-10-27T13:00Z", "intensity": INTENSITY},
    {"from": "2026-10-27T13:00Z", "to": "2026-10-27T13:30Z", "intensity": INTENSITY},
    #half-hour gap
    {"from": "2026-10-27T14:00Z", "to": "2026-10-27T14:30Z", "intensity": INTENSITY}, 
]

def test_forecast_response_accepts_api_format():
    data = ForecastResponse.model_validate({"data":DATA[:3]}).data
    assert len(data) == 3

def test_forecast_response_rejects_gap():
    with pytest.raises(ValidationError):
        ForecastResponse.model_validate({"data":DATA})


# ----- test validation of ChargeRequest --------

VALID_CHARGE_REQUEST = {
    "charge_needed_kwh": 20.5,
    "charge_rate_kw": 7.0,
    "deadline": "2026-10-28T12:00Z",
    "mode": "discrete",
}

def test_chargerequest_accepts_valid_input():
    request = ChargeRequest.model_validate(VALID_CHARGE_REQUEST)
    assert request.charge_needed_kwh == 20.5
    assert request.charge_rate_kw == 7.0
    assert request.deadline.tzinfo is not None
    assert request.mode == "discrete"

def test_no_mode_gives_discrete_in_chargerequest():
    charge_request = {k: v for k,v in VALID_CHARGE_REQUEST.items() if k != "mode"}
    request = ChargeRequest.model_validate(charge_request)
    assert request.mode == "discrete"

@pytest.mark.parametrize("mode",["discrete", "continuous"])
def test_chargerequest_accepts_all_mode_values(mode):
    request = ChargeRequest.model_validate(VALID_CHARGE_REQUEST | {"mode": mode})
    assert request.mode == mode

def test_chargerequest_converts_to_utc():
    request = ChargeRequest.model_validate(VALID_CHARGE_REQUEST | {"deadline": "2026-10-28T13:00+01:00"})
    assert request.deadline.hour == 12
    assert request.deadline.tzinfo == timezone.utc


@pytest.mark.parametrize("params_to_change, slots_needed_expected",[
    ({"charge_needed_kwh": 20.5, "charge_rate_kw": 7.0}, 6),     # 5.86 same as test valid request but here for clarity
    ({"charge_needed_kwh": 2.1, "charge_rate_kw": 0.7}, 6),      # 6.0(0)1 is 6 floating-point error should not be rounded up
    ({"charge_needed_kwh": 28, "charge_rate_kw": 7}, 8),         # exact fit
])
def test_chargerequest_slots_needed_is_correct(params_to_change,slots_needed_expected):
    request = ChargeRequest.model_validate(VALID_CHARGE_REQUEST | params_to_change)
    assert request.slots_needed == slots_needed_expected

@pytest.mark.parametrize("field, value",[
    pytest.param("charge_needed_kwh", MAX_CHARGE_KWH, id="charge_needed_kwh at max"),
    pytest.param("charge_needed_kwh", MIN_CHARGE_KWH + 1e-6, id="charge_needed_kwh just above minimum"),
    pytest.param("charge_rate_kw", MAX_CHARGE_RATE_KW, id="charge_rate_kw at max"),
    pytest.param("charge_rate_kw", MIN_CHARGE_RATE_KW + 1e-6, id="charge_rate_kw just above min"),
],)
def test_chargerequest_accepts_charge_and_charge_rate_boundary_values(field, value):
    request = ChargeRequest.model_validate(VALID_CHARGE_REQUEST | {field: value})
    assert getattr(request, field) == value

@pytest.mark.parametrize("bad_input",[
    pytest.param({"charge_needed_kwh": MIN_CHARGE_KWH - 1}, id="charge_needed_kwh less than min"),
    pytest.param({"charge_needed_kwh": MIN_CHARGE_KWH}, id="charge_needed_kwh at min"),
    pytest.param({"charge_needed_kwh": MAX_CHARGE_KWH + 1e-6}, id="charge_needed_kwh above max"),
    pytest.param({"charge_rate_kw": MIN_CHARGE_RATE_KW - 1}, id="charge_rate_kw less than min"),
    pytest.param({"charge_rate_kw": MIN_CHARGE_RATE_KW}, id="charge_rate_kw at min"),
    pytest.param({"charge_rate_kw": MAX_CHARGE_RATE_KW + 1e-6}, id="charge_rate_kw above max"),
    pytest.param({"mode": "slots"}, id="mode is incorrect string"),
    pytest.param({"mode": "Discrete"}, id="mode is capitalised"),
    pytest.param({"deadline": "2026-10-28T12:00"}, id="date with no timezone info"),
    pytest.param({"charge_needed_kwh": MIN_CHARGE_KWH / 2}, id="charge_needed_kwh positive but below min"),
],)
def test_chargerequest_rejects_invalid_input(bad_input):
    with pytest.raises(ValidationError):
        ChargeRequest.model_validate(VALID_CHARGE_REQUEST | bad_input)

def test_chargerequest_is_frozen():
    request = ChargeRequest.model_validate(VALID_CHARGE_REQUEST)
    with pytest.raises(ValidationError):
        request.charge_needed_kwh = 15 # type: ignore[misc]

def test_chargerequest_rejects_input_with_missing_field():
    charge_request = {k: v for k,v in VALID_CHARGE_REQUEST.items() if k != "charge_needed_kwh"}
    with pytest.raises(ValidationError):
        ChargeRequest.model_validate(charge_request)

def test_smallest_charge_at_highest_power_needs_a_slot():
    request = ChargeRequest.model_validate(VALID_CHARGE_REQUEST | {
        "charge_needed_kwh": MIN_CHARGE_KWH * 1.01,
        "charge_rate_kw": MAX_CHARGE_RATE_KW,
    })
    assert request.slots_needed >= 1
