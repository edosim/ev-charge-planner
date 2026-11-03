
import asyncio
from datetime import datetime, timezone, timedelta

import httpx
from pydantic import (
    BaseModel,
    Field,
    AwareDatetime,
    field_validator,
    model_validator,
    ConfigDict,
)
from typing import Self, Literal, assert_never

import math #for ceil

from helper_functions import get_smallest_window

# Carbon Intensity API models

class Intensity(BaseModel):
    forecast: int | None = Field(ge=0)
    actual: int | None = None
    index: Literal["very low", "low", "moderate", "high", "very high"]


class Slot(BaseModel):
    start: AwareDatetime = Field(alias="from")
    end: AwareDatetime = Field(alias="to")
    intensity: Intensity

    @field_validator("start", "end")
    @classmethod
    def to_utc(cls, value: datetime) -> datetime:
        """Converts `start` and `end` fields to UTC"""
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def check_half_hour(self) -> Self:
        """Checks that slot end is exactly 30 min after start."""
        if self.end - self.start != timedelta(minutes=30):
            raise ValueError("A slot must be 30 minutes long. "
                             f"Got {(self.end - self.start).total_seconds()/60} minutes")
        return self

class ForecastResponse(BaseModel):
    data: list[Slot]

    @model_validator(mode="after")
    def check_consecutive(self) -> Self:
        """Check that a slot end time is the same as the next's start time"""
        for previous, current in zip(self.data[:-1],self.data[1:]):
            if previous.end != current.start:
                raise ValueError("Slots must be consecutive. Found a gap after"
                                 f"{previous.end:%Y-%m-%d %H:%M} UTC")
        return self

# API request models

class ChargeRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    charge_needed_kwh: float = Field(gt=0, le=200)
    charge_rate_kw: float = Field(gt=0, le=400)
    deadline: AwareDatetime
    mode: Literal["discrete", "continuous"] = "discrete"

    @field_validator("deadline")
    @classmethod
    def to_utc(cls, value: datetime) -> datetime:
        """Converts `deadline` field to UTC"""
        return value.astimezone(timezone.utc)

    @property
    def slots_needed(self) -> int:
        """Number of half-hour needed to charge, rounded up"""
        half_hours = self.charge_needed_kwh / self.charge_rate_kw * 2
        # round first to remove floating-point noise e.g. 2.1/0.7*2 = 6.0(0)01
        return math.ceil(round(half_hours,6))


BASE_URL = "https://api.carbonintensity.org.uk"


async def fetch_forecast(client: httpx.AsyncClient) -> list[Slot]:
    """Fetch data from Carbon intensity API. Return slots up to the where
    `slot.intensity.forecast is None`."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")

    resp = await client.get(f"{BASE_URL}/intensity/{now}/fw48h", timeout=10)
    resp.raise_for_status()
    slots = ForecastResponse.model_validate(resp.json()).data

    slots_usable = []
    for slot in slots:
        if slot.intensity.forecast is None:
            break
        slots_usable.append(slot)
    return slots_usable




def plan_charge(slots: list[Slot], request: ChargeRequest) -> tuple[list[Slot], bool]:
    """Returns slots of planned charge and `bool` of whether it gets fully charged"""
    
    slots_available = [s for s in slots if s.end <= request.deadline]
    # If there are not enough slots charge now.
    if request.slots_needed > len(slots_available):
        return slots_available, False
    else:
        match request.mode:
            case "discrete":
                # Find the best slots overall
                greenest_slots = sorted(slots_available, key = lambda s: s.intensity.forecast)[:request.slots_needed]
                return sorted(greenest_slots, key = lambda s: s.start), True
            case "continuous":
                #get index of first item in the window with lowest total forecast
                idx,_ = get_smallest_window([s.intensity.forecast for s in slots_available],
                                            request.slots_needed)
                return slots_available[idx:idx + request.slots_needed], True
            case _:
                assert_never(request.mode)

def emissions_kg(slots: list[Slot], charge_rate_kw):
    grams_per_energy = sum([s.intensity.forecast for s in slots])
    grams = charge_rate_kw * 0.5 * grams_per_energy
    return grams * 1e-3

async def main():
    async with httpx.AsyncClient() as client:
        slots = await fetch_forecast(client)

    print(f"Got {len(slots)} slots")
    for slot in slots[:3]+slots[-3:]:
        print(slot.start, slot.intensity.forecast, slot.intensity.actual, slot.intensity.index)

    deadline = datetime.now(timezone.utc) + timedelta(hours=1)

    request_input = {
        "charge_needed_kwh": 30,
        "charge_rate_kw": 7,
        "deadline": deadline,
        "mode": "continuous",
    }
    request = ChargeRequest.model_validate(request_input)
    plan, fully_charged = plan_charge(slots, request)

    if not fully_charged:
        charge_final = request.charge_rate_kw / 2 * len(plan)
        print(f"There is not enough time for a full charge. Your vehicle will get {charge_final} kWh.")

    print("Your vehicle will charge at the following times.")
    for s in plan:
        print(f"{s.start.strftime('%a %H:%M')} UTC")

    #Emissions saved
    dumb = emissions_kg(slots[:len(plan)], request.charge_rate_kw)
    smart = emissions_kg(plan, request.charge_rate_kw)
    print(f"You will save {dumb-smart:.2f} kg of CO2 vs. charging now.")
    if request.mode == "continuous":
        request_discrete = ChargeRequest.model_validate(request_input | {"mode": "discrete"})
        plan_discrete, _ = plan_charge(slots, request_discrete)
        smart_discrete = emissions_kg(plan_discrete, request.charge_rate_kw)
        print(f"Choose discrete mode and save an extra {smart - smart_discrete:.2f} kg of CO2.")


if __name__ == "__main__":
    asyncio.run(main())


