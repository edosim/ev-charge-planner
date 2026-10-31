"""Tests for the API: [functions]
"""

import pytest
from helpers import make_slots, T0, FAR_FUTURE


from datetime import datetime, time, timedelta, date, timezone
import httpx
from fastapi.testclient import TestClient

from api import check_deadline, app, get_client, UK
from main import Slot

# ----- check_deadline: past and after 48h deadlines ----

def test_deadline_in_range_is_accepted():
    slots = (make_slots([50,]*30))
    deadline = slots[1].end
    check_deadline(deadline, slots, now=T0)


def test_deadline_in_the_past_raises_error():
    slots = (make_slots([50,]*30))
    deadline = T0 - timedelta(hours=1)
    with pytest.raises(ValueError, match="future"):
        check_deadline(deadline, slots, now=T0)

def test_deadline_now_raises_error():
    slots = (make_slots([50,]*30))
    with pytest.raises(ValueError, match="future"):
        check_deadline(T0, slots, now=T0)


def test_deadline_after_last_slot_raises_error():
    slots = (make_slots([50,]*30))
    deadline = FAR_FUTURE
    with pytest.raises(ValueError, match="48h"):
        check_deadline(deadline, slots, now=T0)

def test_deadline_equal_last_slot_is_accepted():
    slots = (make_slots([50,]*30))
    deadline = slots[-1].end
    check_deadline(deadline, slots, now=T0)

# ---------------- test api ---
# helper functions

def start_of_first_slot() -> datetime:
    """Get time of first slot as a datetime object"""
    now = datetime.now(timezone.utc)
    minutes_to_subtract = now.minute % 30
    first_slot_time =  now - timedelta(minutes=minutes_to_subtract)
    return first_slot_time.replace(second=0, microsecond=0)

def forecast_json(forecasts: list[int]):
    """Create the json Carbon Intensity API would return"""
    slots = make_slots(forecasts, start=start_of_first_slot())
    return {"data": [s.model_dump(mode='json', by_alias=True) for s in slots]}


def fake_server(forecasts=None, status=200, body=None):
    """Make the app talk to a fake Carbon Intensity API."""
    if body is None:
        body = forecast_json(forecasts if forecasts is not None else [50] * 96) #48h

    def handler(request):
        # what response to give (status+json)
        return httpx.Response(status, json=body)

    fake = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    app.dependency_overrides[get_client] = lambda: fake


@pytest.fixture
def client():
    yield TestClient(app)
    app.dependency_overrides.clear()

def query_params(hours_from_now: float,
                 charge_needed_kwh: float = 30,
                 **extra) -> dict:
    """Query parameters with deadline N hours from now, UK time.
    The extra params are charge_rate_kw=7 and mode='discrete'."""
    d = datetime.now(UK) + timedelta(hours=hours_from_now)
    return {
        "charge_needed_kwh": charge_needed_kwh,
        "deadline_date": d.date().isoformat(),
        "deadline_time": d.strftime("%H:%M"),
        **extra,
    }



#----- all works----

def test_returns_a_plan_and_full_forecast(client):
    fake_server()
    response = client.get("/schedule",params=query_params(10))
    assert response.status_code == 200
    assert len(response.json()["slots"]) == 9 # successful slots for 30kWh at 7kW
    assert len(response.json()["forecast"]) == 96 # 48h of data


def test_returns_correct_discrete_plan(client):
    fake_server(forecasts=[50,20,50,25,50,10] + [100]*90)
    response = client.get("/schedule",params=query_params(10, charge_needed_kwh=7))

    assert response.status_code == 200
    forecast = [s['intensity']['forecast'] for s in response.json()["slots"]]
    assert forecast == [20,10]

def test_returns_correct_continuous_plan(client):
    fake_server(forecasts=[50,20,50,25,50,10] + [100]*90)
    response = client.get("/schedule",params=query_params(10, charge_needed_kwh=7,mode='continuous'))

    assert response.status_code == 200
    forecast = [s['intensity']['forecast'] for s in response.json()["slots"]]
    assert forecast == [50,10]

def test_plan_ends_before_deadline(client):
    fake_server()
    ps = query_params(10)
    response = client.get("/schedule",params=ps)

    plan_end_time = response.json()["slots"][-1]['to']
    plan_end_time = datetime.fromisoformat(plan_end_time)

    deadline = datetime.fromisoformat(f'{ps["deadline_date"]}T{ps["deadline_time"]}')
    deadline = deadline.replace(tzinfo=UK)
    assert plan_end_time <= deadline


def test_emissions_are_correct(client):
    fake_server(forecasts=[200, 200, 50,100] + [200]*92)
    response = client.get("/schedule",params=query_params(10, charge_needed_kwh=7))
    # emissions (50+100) * 0.5 * 7 * 1e-3
    assert response.json()['emissions_kg'] == pytest.approx(0.525)
    assert response.json()['charge_now_kg'] == pytest.approx(1.4)
    assert response.json()['saved_kg'] == pytest.approx(0.875)

def test_emissions_have_3_dp(client):
    fake_server(forecasts=[50, 50] + [200]*94)
    response = client.get("/schedule",params=query_params(10, charge_needed_kwh=6, charge_rate_kw=20/3))
    # emissions (50+50) * 0.5 * 20/3 * 1e-3 = 50 * 20/3 * 1e-3 = 0.333(3333)
    assert response.json()['emissions_kg'] == 0.333
    assert response.json()['charge_now_kg'] == 0.333

def test_saved_emissions_have_3_dp(client):
    # make difference 0.0045 so it rounds to 0.004
    # charge now is 19 * 0.5 * 1 *1e-3 = 0.0095
    # discrete is 10 * 0.5 * 1* 1e-3 = 0.005
    fake_server(forecasts=[9, 10, 5, 5] + [200]*92)
    response = client.get("/schedule",params=query_params(10, charge_needed_kwh=1, charge_rate_kw=1))

    assert response.json()['saved_kg'] == 0.004

@pytest.mark.parametrize("hours_from_now, expected_fully_charged",[
    (1, False),      #1 hour is not enough for 30 kWh at 7kW 
    (10, True),     #10 hours are enough for 30 kWh at 7kW 
])
def test_fully_charged_is_correct(client, hours_from_now, expected_fully_charged):
    fake_server()
    response = client.get("/schedule",params=query_params(hours_from_now))
    assert response.json()['fully_charged'] == expected_fully_charged


# --------- deadline errors (check_deadline through API)----------

def test_deadline_in_past_raises_422(client):
    fake_server()
    response = client.get("/schedule",params=query_params(-10))
    assert response.status_code == 422
    assert "future" in response.json()["detail"]

def test_deadline_past_48h_raises_422(client):
    fake_server()
    response = client.get("/schedule",params=query_params(50))
    assert response.status_code == 422
    assert "48h" in response.json()["detail"]


# --------- bad parameters ---------
@pytest.mark.parametrize("bad_param",[
    {'charge_needed_kwh': -10},    #only+ve allowed
    {'charge_needed_kwh': 250},    #only <200 allowed
    {'deadline_date': "27/10/26"},  #only YYYY-MM-DD allowed
    {'deadline_time': '7'},        #only 07:00 allowed
    {'charge_rate_kw': -7},        #only 0<x<400 allowed
    {'charge_rate_kw': 407},       
    {'mode':'fastest'},            #only 'discrete' and 'continuous'
])
def test_bad_params_raises_422(client, bad_param):
    fake_server()
    response = client.get("/schedule",params=query_params(10,**bad_param))
    assert response.status_code == 422


#----------- Carbon Intesntiy API problems -------

def test_api_down_gives_503(client):
    fake_server(status=500, body={})
    assert client.get("/schedule", params=query_params(10)).status_code == 503


def test_api_response_bad_gives_503(client):
    fake_server(body={"data": [{"from": "not date"}]})
    assert client.get("/schedule", params=query_params(10)).status_code == 503


def test_api_empty_gives_503(client):
    fake_server(body={"data": []})
    assert client.get("/schedule", params=query_params(10)).status_code == 503
