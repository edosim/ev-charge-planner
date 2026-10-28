
import asyncio
from datetime import datetime, timezone, timedelta

import httpx
from pydantic import BaseModel, Field

import math #for ceil

import matplotlib.pyplot as plt
import matplotlib.dates as mdates

from helper_functions import get_smallest_window

class Intensity(BaseModel):
    forecast: int | None
    actual: int | None = None
    index: str


class Slot(BaseModel):
    start: datetime = Field(alias="from")
    end: datetime = Field(alias="to")
    intensity: Intensity


class ForecastResponse(BaseModel):
    data: list[Slot]


BASE_URL = "https://api.carbonintensity.org.uk"


async def fetch_forecast(client: httpx.AsyncClient) -> list[Slot]:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")

    resp = await client.get(f"{BASE_URL}/intensity/{now}/fw48h", timeout=10)
    resp.raise_for_status()
    slots = ForecastResponse.model_validate(resp.json()).data
    return [s for s in slots if s.intensity.forecast is not None]




def plan_charge(slots: list[Slot],
                charge_needed: float,
                charge_rate: float,
                deadline: datetime,
                mode: str = 'discrete'):
    if mode not in ('discrete', 'continuous'):
        raise ValueError(f"Got mode = '{mode}'. Expected 'discrete' or 'continuous'.")

    slots_needed = math.ceil(charge_needed/charge_rate * 2)

    slots_available = [s for s in slots if s.end <= deadline]
    # If there are not enough slots charge now.
    if slots_needed > len(slots_available):
        charge_final = charge_rate / 2 *len(slots_available)
        print(f"There is not enough time for a full charge. Your vehicle will get {charge_final} kWh.")
        return slots_available
    else:
        if mode == 'discrete':
            print("Discrete mode")
            # Find the best slots overall
            greenest_slots = sorted(slots_available, key = lambda s: s.intensity.forecast)[:slots_needed]
            return sorted(greenest_slots, key = lambda s: s.start)
        elif mode == 'continuous':
            print('Continuous mode')
            #get index of first item in the window with lowest total forecast
            idx,_ = get_smallest_window([s.intensity.forecast for s in slots_available],
                                        slots_needed)
            return slots_available[idx:idx + slots_needed]

def emissions_kg(slots: list[Slot], charge_rate):
    grams_per_energy = sum([s.intensity.forecast for s in slots])
    grams = charge_rate * 0.5 * grams_per_energy
    return grams * 1e-3

async def main():
    async with httpx.AsyncClient() as client:
        slots = await fetch_forecast(client)

    print(f"Got {len(slots)} slots")
    for slot in slots[:3]+slots[-3:]:
        print(slot.start, slot.intensity.forecast, slot.intensity.actual, slot.intensity.index)

    deadline = datetime.now(timezone.utc) + timedelta(hours=8)

    max_charge = 30 #kWh
    current_charge_fraction = 0.1 # from 0 to 1
    charge_needed = (1-current_charge_fraction) * max_charge
    charge_rate = 7
    mode = 'continuous'
    plan = plan_charge(slots, charge_needed,charge_rate,deadline,mode=mode)


    print("Your vehicle will charge at the following times.")
    for s in plan:
        print(f"{s.start.strftime('%a %H:%M')} UTC")

    #Emissions saved
    dumb = emissions_kg(slots[:len(plan)], charge_rate)
    smart = emissions_kg(plan, charge_rate)
    print(f"You will save {dumb-smart:.2f} kg of CO2 vs. charging now.")
    if mode == 'continuous':
        plan_discrete = plan_charge(slots, charge_needed,charge_rate,deadline,mode='discrete')
        smart_discrete = emissions_kg(plan_discrete, charge_rate)
        print(f"Choose discrete mode and save an extra {smart - smart_discrete:.2f} kg of CO2.")


    
    # plot
    PLOT = False

    if PLOT:
        x = [slot.start for slot in slots]
        y = [slot.intensity.forecast for slot in slots] 
        plt.plot(x,y,'o-')
        ax = plt.gca()
        ax.xaxis.set_major_locator(mdates.HourLocator(byhour=range(0,24,2)))
        ax.xaxis.set_minor_locator(mdates.MinuteLocator(byminute=range(0,60,30)))

        ax.xaxis.set_major_formatter(mdates.DateFormatter('%H'))
        plt.show()
    

if __name__ == "__main__":
    asyncio.run(main())


