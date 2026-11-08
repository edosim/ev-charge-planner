import pytest
from helpers import make_slots, make_prices
from prices import get_total_price
from schemas import SLOT_HOURS

def test_total_price_is_sum_times_energy_per_slot():
    slots = make_slots([50, 50])
    prices = make_prices([10, 30])
    # (10 + 30) p/kWh * 0.5 h * 7 kW = 140 p
    assert get_total_price(prices, slots, 7) == pytest.approx(140)

def test_only_plan_slots_are_priced():
    prices = make_prices([10, 99, 20, 99])
    slots = [make_slots([50] * 4)[i] for i in (0, 2)]   # discrete plan with a gap
    assert get_total_price(prices, slots, 2) == pytest.approx((10 + 20) * SLOT_HOURS * 2)

def test_missing_price_returns_none():
    slots = make_slots([50] * 3)
    prices = make_prices([10, 10])      # last slot not published
    assert get_total_price(prices, slots, 7) is None

def test_no_prices_returns_none():
    assert get_total_price([], make_slots([50]), 7) is None

def test_empty_plan_costs_zero():
    assert get_total_price(make_prices([10]), [], 7) == 0

def test_negative_prices_give_negative_total():
    assert get_total_price(make_prices([-5, -5]), make_slots([50, 50]), 2) == pytest.approx(-10)