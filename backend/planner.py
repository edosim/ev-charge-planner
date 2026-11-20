
from datetime import datetime, timezone
import httpx
from typing import assert_never
from schemas import (
    Slot,
    ForecastResponse,
    ChargeRequest
)

from helper_functions import get_smallest_window


BASE_URL = "https://api.carbonintensity.org.uk"


async def fetch_forecast(client: httpx.AsyncClient,
                         now: datetime | None = None) -> list[Slot]:
    """Fetch data from Carbon intensity API. Return slots up to where
    `slot.intensity.forecast is None`."""
    if now is None:
        now = datetime.now(timezone.utc)
    timestamp = now.strftime("%Y-%m-%dT%H:%MZ")

    resp = await client.get(f"{BASE_URL}/intensity/{timestamp}/fw48h", timeout=10)
    resp.raise_for_status()
    slots = ForecastResponse.model_validate(resp.json()).data

    slots_usable = []
    for slot in slots:
        if slot.intensity.forecast is None:
            break
        slots_usable.append(slot)
    return slots_usable




def plan_charge(slots: list[Slot], request: ChargeRequest) -> tuple[list[Slot], float, bool]:
    """Returns `slots` of planned charge;
    `charge_delivered_kwh`: the energy that will be delivered with the plan;
    and `fully_charged`: `bool` of whether it gets fully charged.
      Note: charge_delivered_kwh will match the requested charge if `fully_charged is True."""
    
    slots_available = [s for s in slots if s.end <= request.deadline]
    # If there are not enough slots charge now.
    if request.slots_needed > len(slots_available):
        charge_delivered_kwh = request.charge_rate_kw * 0.5 * len(slots_available)
        return slots_available, charge_delivered_kwh, False
    else:
        match request.mode:
            case "discrete":
                # Find the best slots overall
                greenest_slots = sorted(slots_available, key = lambda s: s.forecast)[:request.slots_needed]
                return sorted(greenest_slots, key = lambda s: s.start), request.charge_needed_kwh, True
            case "continuous":
                #get index of first item in the window with lowest total forecast
                idx,_ = get_smallest_window([s.forecast for s in slots_available],
                                            request.slots_needed)
                return slots_available[idx:idx + request.slots_needed], request.charge_needed_kwh, True
            case _:
                assert_never(request.mode)

def emissions_kg(slots: list[Slot], request: ChargeRequest) -> float:
    """CO2 emissions in kg for charging in `slots`, in order, until
    `charge_needed_kwh` is delivered. The last slot may be partial."""
    energy_per_slot = request.charge_rate_kw * 0.5
    remaining = request.charge_needed_kwh
    grams = 0.0
    for slot in slots:
        energy = min(energy_per_slot, remaining)
        grams += energy * slot.forecast
        remaining -= energy
    return grams * 1e-3
