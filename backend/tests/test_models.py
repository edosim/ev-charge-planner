"""Test for models used on backend"""

import pytest

from pydantic import ValidationError

from schemas import (
    Intensity, Slot, ForecastResponse,
    Price, PricesResponse,
    ChargeRequest
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

def test_slot_is_frozen():
    slot = Slot.model_validate({"from": "2026-10-28T12:00Z", "to": "2026-10-28T12:30Z", "intensity": INTENSITY})
    with pytest.raises(ValidationError):
        slot.intensity = Intensity.model_validate(INTENSITY | {"index": "low"})

def test_intensity_within_slot_is_frozen():
    slot = Slot.model_validate({"from": "2026-10-28T12:00Z", "to": "2026-10-28T12:30Z", "intensity": INTENSITY})
    with pytest.raises(ValidationError):
        slot.intensity.forecast = 20

# ---- test validation of ForecastResponse ------

DATA = [
    {"from": "2026-10-27T12:00Z", "to": "2026-10-27T12:30Z", "intensity": INTENSITY},
    {"from": "2026-10-27T12:30Z", "to": "2026-10-27T13:00Z", "intensity": INTENSITY},
    {"from": "2026-10-27T13:00Z", "to": "2026-10-27T13:30Z", "intensity": INTENSITY},
    #half-hour gap
    {"from": "2026-10-27T14:00Z", "to": "2026-10-27T14:30Z", "intensity": INTENSITY}, 
]

def test_forecast_response_accepts_api_format():
    response = ForecastResponse.model_validate({"data": DATA[:3]})
    assert len(response.data) == 3

def test_forecast_response_rejects_gap():
    with pytest.raises(ValidationError):
        ForecastResponse.model_validate({"data": DATA})


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
    assert request.deadline.utcoffset().total_seconds() == 0


@pytest.mark.parametrize("params_to_change, slots_needed_expected",[
    ({"charge_needed_kwh": 20.5, "charge_rate_kw": 7.0}, 6),     # 5.86 same as valid request but here for clarity
    ({"charge_needed_kwh": 2.1, "charge_rate_kw": 0.7}, 6),      # 6.0(0)1 is 6 floating-point error should not be rounded up
    ({"charge_needed_kwh": 28, "charge_rate_kw": 7}, 8),         # exact fit
])
def test_chargerequest_slots_needed_is_correct(params_to_change,slots_needed_expected):
    request = ChargeRequest.model_validate(VALID_CHARGE_REQUEST | params_to_change)
    assert request.slots_needed == slots_needed_expected


@pytest.mark.parametrize("bad_input",[
    pytest.param({"charge_needed_kwh": -1}, id="charge_needed_kwh is negative"),
    pytest.param({"charge_needed_kwh": 0}, id="charge_needed_kwh is 0"),
    pytest.param({"charge_needed_kwh": 500}, id="charge_needed_kwh > 200"),
    pytest.param({"charge_rate_kw": -1}, id="charge_rate_kw is negative"),
    pytest.param({"charge_rate_kw": 0}, id="charge_rate_kw is 0"),
    pytest.param({"charge_rate_kw": 500}, id="charge_rate_kw > 400"),
    pytest.param({"mode": "slots"}, id="mode is incorrect string"),
    pytest.param({"mode": "Discrete"}, id="mode is capitalised"),
    pytest.param({"deadline": "2026-10-28T12:00"}, id="date with no timezone info")
],)
def test_chargerequest_rejects_invalid_input(bad_input):
    with pytest.raises(ValidationError):
        ChargeRequest.model_validate(VALID_CHARGE_REQUEST | bad_input)

def test_chargerequest_is_frozen():
    request = ChargeRequest.model_validate(VALID_CHARGE_REQUEST)
    with pytest.raises(ValidationError):
        request.charge_needed_kwh = 15

def test_chargerequest_rejects_input_with_missing_field():
    charge_request = {k: v for k,v in VALID_CHARGE_REQUEST.items() if k != "charge_needed_kwh"}
    with pytest.raises(ValidationError):
        ChargeRequest.model_validate(charge_request)


# Test validation of agile API response
OCTOPUS_RESPONSE = {
    "count": 2,
    "next": None,
    "previous": None,
    "results": [
        {
        "value_exc_vat": 41.94,
        "value_inc_vat": 41.94,
        "valid_from": "2026-11-06T22:30:00Z",
        "valid_to": "2026-11-06T23:00:00Z",
        "payment_method": None
        },
        {
        "value_exc_vat": 42.91,
        "value_inc_vat": 42.91,
        "valid_from": "2026-11-06T22:00:00Z",
        "valid_to": "2026-11-06T22:30:00Z",
        "payment_method": None
        },
    ]
}

# Price half an hour earlier to simulate gap
PRICE = {
    "value_exc_vat": 42.91,
    "value_inc_vat": 42.91,
    "valid_from": "2026-11-06T21:00:00Z",
    "valid_to": "2026-11-06T21:30:00Z",
    "payment_method": None
}

# ---------- Test PricesResponse -------------

def test_price_response_accepts_valid_response_and_sorts_prices():
    response = PricesResponse.model_validate(OCTOPUS_RESPONSE)
    assert response.count == 2
    assert response.next == None
    assert response.previous == None
    assert len(response.prices) == 2
    assert response.prices[0].start < response.prices[1].start

def test_price_response_rejects_gap():
    # Add price to OCTOPUS_RESPONSE that ends half an hour before the first price in prices
    response_gapped = OCTOPUS_RESPONSE | {"results": OCTOPUS_RESPONSE["results"] + [PRICE]}
    with pytest.raises(ValidationError):
        PricesResponse.model_validate(response_gapped)

# -------- Test Price -----------

def test_price_accepts_api_format():
    price = Price.model_validate(PRICE)
    assert price.value_exc_vat == 42.91
    assert price.start.tzinfo is not None

def test_price_converts_to_utc():
    price_response = (PRICE
                    | {"valid_from": "2026-11-06T21:00:00+01:00",
                       "valid_to": "2026-11-06T21:30:00+01:00"})
    price = Price.model_validate(price_response)
    assert price.start.hour == 20
    assert price.start.utcoffset().total_seconds() == 0

def test_price_rejects_time_without_timezone():
    price_response = (PRICE | {"valid_from": "2026-11-06T21:00:00",
                               "valid_to": "2026-11-06T21:30:00"})

    with pytest.raises(ValidationError):
        Price.model_validate(price_response)

def test_price_rejects_wrong_slot_length():
    price_response = (PRICE | {"valid_from": "2026-11-06T20:30:00Z"})
    with pytest.raises(ValidationError):
        Price.model_validate(price_response)

def test_price_is_frozen():
    price = Price.model_validate(PRICE)
    with pytest.raises(ValidationError):
        price.count = 1
