"""Test for the charging planner: plan_charge, emissions_kg, get_smallest_window"""


import pytest
from helpers import make_slots, T0, FAR_FUTURE


from datetime import datetime, timedelta, timezone


from helper_functions import get_smallest_window
from main import Slot, emissions_kg, plan_charge, ChargeRequest





# -------- get_smallest_window -----------
@pytest.mark.parametrize("nums, n, expected_idx", [
    ([1, 1, 9, 9, 9], 2, 0),     # best window at the start
    ([9, 9, 1, 1, 9], 2, 2),     # best window in the middle
    ([9, 9, 9, 1, 1], 2, 3),     # best window at the end
    ([5, 5, 5, 5, 5], 2, 0),     # more than one valid -> the first valid window
    ([3, 1, 2], 3, 0),           # window as long as the whole list
])
def test_smallest_window_finds_lowest_sum(nums, n, expected_idx):
    idx, window = get_smallest_window(nums, n)
    assert idx == expected_idx
    assert window == nums[idx:idx + n]


# -------- emissions_kg --------------
def test_emissions_kg():
    # 50 and 100 gCO2/kWh; charge rate 7 kW: 3.5 kWh per 30 min
    # (50+100) * 0.5 * 7 *1e-3 = 150 * 3.5 * 1e-3 = 0.525 kg
    assert emissions_kg(make_slots([50,100]), 7) == pytest.approx(0.525)

def test_emissions_kg_of_empty_plan_is_zero():
    assert emissions_kg([], 7) == 0


# --------- plan_charge: number of slots -----------
@pytest.mark.parametrize("charge_needed_kwh, charge_rate_kw, expected_slots",[
    (3.5, 7, 1),    #exactly 30 min
    (3.6, 7, 2),    # slightly more than 30 min: round up
    (10.5, 7, 3),   # 3 * 30 min
    (20, 7, 6),     # 20 / 3.5 = 5.7 -> 6
    (30, 7, 9),     #30 / 3.5 = 8.6 -> 9
])
@pytest.mark.parametrize("mode", ["discrete", "continuous"])
def test_plan_uses_correct_number_of_slots(charge_needed_kwh, charge_rate_kw, expected_slots, mode):
    slots = (make_slots([50,]*30))
    request = ChargeRequest(charge_needed_kwh=charge_needed_kwh, charge_rate_kw=charge_rate_kw, deadline=FAR_FUTURE, mode=mode)
    plan, _ = plan_charge(slots, request)
    assert len(plan) == expected_slots


# ----- plan_charge: slot selection -----

def test_discrete_chooses_greenest_slots_overall_in_time_order():
    slots = make_slots([50, 100, 40, 70, 30])
    request = ChargeRequest(charge_needed_kwh=7, charge_rate_kw=7, deadline=FAR_FUTURE, mode="discrete")
    plan, _ = plan_charge(slots, request)
    assert [s.intensity.forecast for s in plan] == [40, 30]
    assert [s.start for s in plan] == sorted([s.start for s in plan])


def test_continuous_chooses_greenest_continuous_window():
    #discrete chooses 10, 50. continuous should choose 50, 50
    slots = make_slots([10, 100, 50, 50, 100])
    request = ChargeRequest(charge_needed_kwh=7, charge_rate_kw=7, deadline=FAR_FUTURE, mode="continuous")
    plan, _ = plan_charge(slots, request)
    assert [s.intensity.forecast for s in plan] == [50, 50]


def test_continuous_has_no_time_gaps():
    # check order of four slots
    slots = make_slots([40, 100, 50, 50, 100, 30, 80, 20])
    request = ChargeRequest(charge_needed_kwh=14, charge_rate_kw=7, deadline=FAR_FUTURE, mode="continuous")
    plan, _ = plan_charge(slots, request)
    for first, second in zip(plan[:-1], plan[1:]):
        assert first.end == second.start


def test_discreet_never_worse_than_continuous():
    # discreet must always be better or the same as continuous
    slots = make_slots([40, 100, 50, 50, 100, 30, 80, 20, 40, 150, 15, 90])
    # check for different length
    for charge_needed_kwh in [3.5, 7, 10.5, 20, 30]:
        request_continuous = ChargeRequest(charge_needed_kwh=charge_needed_kwh, charge_rate_kw=7, deadline=FAR_FUTURE, mode="continuous")
        request_discrete = ChargeRequest(charge_needed_kwh=charge_needed_kwh, charge_rate_kw=7, deadline=FAR_FUTURE, mode="discrete")

        continuous, _ = plan_charge(slots, request_continuous)
        discrete, _ = plan_charge(slots, request_discrete)

        assert emissions_kg(discrete, 7) <= emissions_kg(continuous, 7)

# --------plan_charge: deadline ------

@pytest.mark.parametrize("mode", ["discrete", "continuous"])
def test_slots_after_deadline_are_ignored(mode):
    slots = make_slots([40, 50, 60, 1, 1]) # the best slots are at the end
    deadline = slots[2].end
    request = ChargeRequest(charge_needed_kwh=7, charge_rate_kw=7, deadline=deadline, mode=mode)
    plan, _ = plan_charge(slots, request)
    assert [s.intensity.forecast for s in plan] == [40, 50]

def test_slot_ending_at_deadline_is_allowed():
    # deadline at 7am, the 6.30-7am slot should be allowed
    slots = make_slots([100, 50])
    deadline = slots[1].end
    request = ChargeRequest(charge_needed_kwh=3.5, charge_rate_kw=7, deadline=deadline)
    plan, _ = plan_charge(slots, request)
    assert [s.intensity.forecast for s in plan] == [50]

# --------plan_charge: fully charged bool ------

@pytest.mark.parametrize("mode", ["discrete", "continuous"])
def test_not_enough_time_to_charge_to_completion(mode):
    slots = make_slots([100, 50, 10, 40])
    deadline = slots[1].end  # 2 slots before deadline
    request = ChargeRequest(charge_needed_kwh=14, charge_rate_kw=7, deadline=deadline, mode=mode)
    plan, fully_charged = plan_charge(slots, request) #4 slots needed to charge fully
    assert [s.intensity.forecast for s in plan] == [100, 50]
    assert fully_charged == False

    
@pytest.mark.parametrize("mode", ["discrete", "continuous"])
def test_enough_time_to_charge_to_completion(mode):
    slots = make_slots([100, 50, 10, 40])
    request = ChargeRequest(charge_needed_kwh=7, charge_rate_kw=7, deadline=FAR_FUTURE, mode=mode)
    plan, fully_charged = plan_charge(slots, request) #2 slots needed
    assert fully_charged == True


