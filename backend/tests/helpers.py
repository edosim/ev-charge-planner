"""Helper functions used in different test files"""

from datetime import datetime, timedelta, timezone

from schemas import Slot, Price

T0 = datetime(2026, 10, 27, 12, 0, tzinfo=timezone.utc)
FAR_FUTURE = T0 + timedelta(days=4)


def make_slots(forecasts: list[int], start: datetime = T0) -> list[Slot]:
    """Build a list of consecutive half-hour slot with `forecasts`."""
    slots = []
    for forecast in forecasts:
        slots.append(Slot.model_validate({
            "from": start,
            "to": start + timedelta(minutes=30),
            "intensity": {"forecast": forecast, "index": "moderate"}
        }))
        start = start + timedelta(minutes=30)
    return slots

def make_prices(values: list[float], start: datetime = T0) -> list[Price]:
    """List of consecutive half-hour Agile prices (p/kWh) starting at `start`."""
    prices = []
    for v in values:
        prices.append(Price.model_validate({
            "value_exc_vat": v, "value_inc_vat": v,
            "valid_from": start, "valid_to": start + timedelta(minutes=30),
            "payment_method": None,
        }))
        start += timedelta(minutes=30)
    return prices