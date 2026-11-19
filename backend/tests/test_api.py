"""Tests for the API: [functions]
"""

import pytest
from helpers import make_slots, T0, FAR_FUTURE


from datetime import datetime, date, time, timedelta, timezone
import httpx
from fastapi.testclient import TestClient

from api import (
    deadline_in_the_future,
    deadline_in_forecast,
    uk_deadline,
    app,
    get_client,
    get_now,
    UK
)
                 
from constants import (
    MAX_CHARGE_KWH, MIN_CHARGE_KWH,
    MAX_CHARGE_RATE_KW, MIN_CHARGE_RATE_KW,
    UK,
)

# ---- uk_deadline ------
@pytest.mark.parametrize("date_deadline, expected",[
    pytest.param(date(2026, 6, 21),
                 datetime(2026, 6, 21, 11, 0, tzinfo=timezone.utc),
                 id="summer"),
    pytest.param(date(2025, 12, 21),
                 datetime(2025, 12, 21, 12, 0, tzinfo=timezone.utc),
                 id="winter"),
],)
def test_uk_deadline_handles_clock_changes(date_deadline, expected):
    time_deadline = time(12,0)
    assert uk_deadline(date_deadline, time_deadline) == expected

def test_uk_raises_when_time_does_not_exist():
    # Clocks go forward 1am becomes 2am
    date_deadline = date(2027, 3, 28)
    time_deadline = time(1,30)
    with pytest.raises(ValueError, match="does not exist"):
        uk_deadline(date_deadline, time_deadline)

def test_repeated_time_when_clocks_go_back_is_the_first():
    # clocks go back: 2am becomes 1am
    deadline = uk_deadline(date(2026, 10, 25), time(1, 30))
    assert deadline.astimezone(timezone.utc) == datetime(2026, 10, 25, 0, 30, tzinfo=timezone.utc)

def test_time_with_timezone_raises():
    date_deadline = date(2026, 11, 1)
    time_deadline = time(12, 30, tzinfo=timezone.utc)
    with pytest.raises(ValueError, match="without a time zone"):
        uk_deadline(date_deadline, time_deadline)


# ----- check deadline: after 48h -------------

def test_deadline_in_range_is_accepted():
    slots = (make_slots([50,]*30))
    deadline = slots[1].end
    deadline_in_forecast(deadline, slots)

def test_deadline_after_last_slot_raises_error():
    slots = (make_slots([50,]*30))
    deadline = FAR_FUTURE
    with pytest.raises(ValueError, match="48h"):
        deadline_in_forecast(deadline, slots)

def test_deadline_equal_last_slot_is_accepted():
    slots = (make_slots([50,]*30))
    deadline = slots[-1].end
    deadline_in_forecast(deadline, slots)

# ----- check deadline: in the past -------------
def test_deadline_in_the_past_raises_error():
    slots = (make_slots([50,]*30))
    deadline = T0 - timedelta(hours=1)
    with pytest.raises(ValueError, match="future"):
        deadline_in_the_future(deadline, now=T0)

def test_deadline_now_raises_error():
    slots = (make_slots([50,]*30))
    with pytest.raises(ValueError, match="future"):
        deadline_in_the_future(T0, now=T0)



# ---------------- test api ---
# helper functions


def forecast_json(forecasts: list[int]):
    """Create the json Carbon Intensity API would return"""
    slots = make_slots(forecasts, start=T0)
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
    app.dependency_overrides[get_now] = lambda: T0


@pytest.fixture
def client():
    # send HTTP requests to app without starting a server
    yield TestClient(app)
    app.dependency_overrides.clear()

def query_params(hours_from_now: float,
                 charge_needed_kwh: float = 30,
                 **extra) -> dict:
    """Query parameters with deadline N hours from now, UK time.
    The extra params are charge_rate_kw=7 and mode='discrete'."""
    d = T0 + timedelta(hours=hours_from_now)
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
    response = client.get("/schedule",params=query_params(10, charge_needed_kwh=20/3, charge_rate_kw=20/3))
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

def test_delivered_charg_kwh_has_2_dp(client):
    fake_server(forecasts=[50, 50] + [200]*94)
    response = client.get("/schedule",params=query_params(10, charge_needed_kwh=3.66666, charge_rate_kw=7))

    assert response.json()['charge_delivered_kwh'] == 3.67


@pytest.mark.parametrize("hours_from_now, expected_fully_charged",[
    (1, False),      #1 hour is not enough for 30 kWh at 7kW 
    (10, True),     #10 hours are enough for 30 kWh at 7kW 
])
def test_fully_charged_is_correct(client, hours_from_now, expected_fully_charged):
    fake_server()
    response = client.get("/schedule",params=query_params(hours_from_now))
    assert response.json()['fully_charged'] == expected_fully_charged


# --------- deadline errors (check deadline through API)----------

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


# --------- test min and max charge needed and charge rate -----
@pytest.mark.parametrize("param",[
    pytest.param({"charge_needed_kwh": MAX_CHARGE_KWH}, id="charge_needed_kwh at max"),
    pytest.param({"charge_rate_kw": MAX_CHARGE_RATE_KW}, id="charge_rate_kw at max"),
    pytest.param({"charge_rate_kw": MIN_CHARGE_RATE_KW + 1e-6}, id="charge_rate_kw just above min"),
],)
def test_accepts_charge_and_charge_rate_boundary_values(client, param):
    fake_server()
    response = client.get("/schedule",params=query_params(10, **param))
    assert response.status_code == 200

def test_charge_needed_kwh_just_above_minimum_gives_one_slot(client):
    
    fake_server()
    response = client.get("/schedule",params=query_params(10, charge_needed_kwh=MIN_CHARGE_KWH + 1e-6))
    assert len(response.json()["slots"]) == 1

@pytest.mark.parametrize("bad_param",[
    pytest.param({"charge_needed_kwh": MIN_CHARGE_KWH - 1}, id="charge_needed_kwh less than min"),
    pytest.param({"charge_needed_kwh": MIN_CHARGE_KWH}, id="charge_needed_kwh at min"),
    pytest.param({"charge_needed_kwh": MIN_CHARGE_KWH / 2}, id="charge_needed_kwh positive but below min"),
    pytest.param({"charge_needed_kwh": MAX_CHARGE_KWH + 1e-6}, id="charge_needed_kwh above max"),
    pytest.param({"charge_rate_kw": MIN_CHARGE_RATE_KW - 1}, id="charge_rate_kw less than min"),
    pytest.param({"charge_rate_kw": MIN_CHARGE_RATE_KW}, id="charge_rate_kw at min"),
    pytest.param({"charge_rate_kw": MAX_CHARGE_RATE_KW + 1e-6}, id="charge_rate_kw above max"),
],)
def test_bad_charge_and_charge_rate_boundary_values_raises_422(client, bad_param):
    fake_server()
    response = client.get("/schedule",params=query_params(10,**bad_param))
    assert response.status_code == 422



# --------- bad mode ---------
@pytest.mark.parametrize("bad_param",[
    {'mode':'fastest'},            #only 'discrete' and 'continuous'
    {"mode": "Discrete"},           # capitalised
])
def test_bad_params_raises_422(client, bad_param):
    fake_server()
    response = client.get("/schedule",params=query_params(10,**bad_param))
    assert response.status_code == 422


#----------- Carbon Intensity API problems -------

def test_api_down_gives_503(client):
    fake_server(status=500, body={})
    assert client.get("/schedule", params=query_params(10)).status_code == 503


def test_api_response_bad_gives_503(client):
    fake_server(body={"data": [{"from": "not date"}]})
    assert client.get("/schedule", params=query_params(10)).status_code == 503


def test_api_empty_gives_503(client):
    fake_server(body={"data": []})
    assert client.get("/schedule", params=query_params(10)).status_code == 503


def fake_server_text(status=200, body = "data"):
    """Make the app talk to a fake Carbon Intensity API that returns text"""

    def handler(request):
        # what response to give (status+text)
        return httpx.Response(status, text=body)

    fake = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    app.dependency_overrides[get_client] = lambda: fake
    app.dependency_overrides[get_now] = lambda: T0


def test_api_not_json_gives_503(client):
    fake_server_text(status=200)
    assert client.get("/schedule", params=query_params(10)).status_code == 503

# ---- test handling of in progress slots ----
def test_in_progress_slot_is_not_chosen(client):
    # The current slot is the greenest
    fake_server(forecasts=[1] + [100] * 95)
    app.dependency_overrides[get_now] = lambda: T0 + timedelta(minutes=10)

    response = client.get("/schedule", params=query_params(10, charge_needed_kwh=3.5))

    assert response.status_code == 200
    forecasts = [s["intensity"]["forecast"] for s in response.json()["slots"]]
    assert 1 not in forecasts

def test_slot_starting_exactly_now_is_kept(client):
    fake_server(forecasts=[1] + [100] * 95)

    response = client.get("/schedule", params=query_params(10, charge_needed_kwh=3.5))

    assert response.status_code == 200
    forecasts = [s["intensity"]["forecast"] for s in response.json()["slots"]]
    assert 1 in forecasts


def test_deadline_in_current_half_hour_is_too_soon(client):
    fake_server()

    response = client.get("/schedule", params=query_params(0.2, charge_needed_kwh=3.5))

    assert response.status_code == 422
    assert "too soon" in response.json()["detail"]

def test_deadline_at_end_of_next_slot_is_accepted(client):
    fake_server(forecasts=[10, 20] + [100] * 94)
    # now at 12:10
    app.dependency_overrides[get_now] = lambda: T0 + timedelta(minutes=15)

    # deadline at 13:00
    response = client.get("/schedule", params=query_params(1, charge_needed_kwh=3.5))

    assert response.status_code == 200
    forecasts = [s["intensity"]["forecast"] for s in response.json()["slots"]]
    assert 20 in forecasts

# --------- test clock changes ----------

def test_nonexisting_deadline_during_clock_change_raises_422(client):
    # Clocks go forward 1am becomes 2am
    fake_server()
    params = {
        "charge_needed_kwh": 30,
        "deadline_date": "2027-03-28",
        "deadline_time": "01:30",
    }
    response = client.get("/schedule", params=params)

    assert response.status_code == 422
    assert "does not exist" in response.json()["detail"]

# ------ test time with timezone is rejected ---
@pytest.mark.parametrize("bad_time", ["07:00+05:00", "07:00Z"])
def test_deadline_time_with_timezone_is_rejected(client, bad_time):
    fake_server()
    params = query_params(10) | {"deadline_time": bad_time}
    response = client.get("/schedule", params=params)
    assert response.status_code == 422
    assert "without a time zone" in response.json()["detail"]
    