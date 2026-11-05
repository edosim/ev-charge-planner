"""Helper functions used in different test files"""

from datetime import datetime, timedelta, timezone

from schemas import Slot

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