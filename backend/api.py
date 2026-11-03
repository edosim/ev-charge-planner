from contextlib import asynccontextmanager
from datetime import datetime, time, timedelta, date, timezone
from typing import Literal
from zoneinfo import ZoneInfo

import httpx
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from pydantic import BaseModel, ValidationError
import json

from main import Slot, ChargeRequest, emissions_kg, fetch_forecast, plan_charge

import os
from pathlib import Path

from fastapi.staticfiles import StaticFiles

UK = ZoneInfo("Europe/London")



@asynccontextmanager
async def lifespan(app: FastAPI):
    async with httpx.AsyncClient() as client:
        app.state.client = client      # created once when the server starts
        yield                          # the server runs here
    # client closed automatically when the server stops


app = FastAPI(title="EV Charge Planner", lifespan=lifespan)

def get_client(request: Request) -> httpx.AsyncClient:
    return request.app.state.client

#  what the endpoint sends back 
class ScheduleResponse(BaseModel):
    slots: list[Slot]
    forecast: list[Slot]
    emissions_kg: float
    charge_now_kg: float
    saved_kg: float
    fully_charged: bool


def check_deadline(deadline: datetime, slots: list[Slot],
                   now: datetime | None = None):
    """Check that the deadline is in the data from the Carbon Intensity API,
    and after now."""
    if now is None:
        now = datetime.now(timezone.utc)
    if deadline <= now:
        raise ValueError("Deadline must be in the future.")
    if deadline > slots[-1].end:
        raise ValueError("Deadline must be within the next 48h "
                         f"(before {slots[-1].end.astimezone(UK):%a %H:%M}).")

# the endpoint

@app.get("/schedule", response_model=ScheduleResponse)
async def schedule(
    charge_needed_kwh: float = Query(gt=0, le=200, description="Energy needed for car in kWh"),
    deadline_date: date = Query(description="Date when the car should finish charging, UK time, e.g. 2026-10-25"),
    deadline_time: time = Query(description="Time when the car should finish charging, UK time, e.g. 07:00"),
    charge_rate_kw: float = Query(7, gt=0, le=400, description="Charge power in kW"),
    mode: Literal["discrete","continuous"] = "discrete",
    client: httpx.AsyncClient = Depends(get_client),
):
    
    try:
        slots = await fetch_forecast(client)
    except (httpx.HTTPError, ValidationError, json.JSONDecodeError):
        raise HTTPException(status_code=503, detail="Carbon Intensity API is unavailable")

    if not slots:
        raise HTTPException(status_code=503, detail="No forecast data available")         
                       
    deadline = datetime.combine(deadline_date, deadline_time, tzinfo=UK)
    request = ChargeRequest(
         charge_needed_kwh = charge_needed_kwh,
         charge_rate_kw = charge_rate_kw,
         deadline = deadline,
         mode = mode
    )

    try:
        check_deadline(request.deadline, slots)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    #Get best slots
    plan, fully_charged = plan_charge(slots, request)
    #Get emissions
    smart_kg = emissions_kg(plan, request.charge_rate_kw)
    now_kg = emissions_kg(slots[:len(plan)], request.charge_rate_kw)
    saved_kg = now_kg - smart_kg

    return ScheduleResponse(slots=plan,
                            forecast=slots,
                            emissions_kg=round(smart_kg,3),
                            charge_now_kg=round(now_kg,3),
                            saved_kg=round(saved_kg, 3), #same precision as two above
                            fully_charged=fully_charged
    )


# Serve the built React page. Must come at the end of file

#get path of distribution of front end
STATIC_DIR = Path(os.environ.get(
    "STATIC_DIR",
    Path(__file__).resolve().parent.parent / "frontend" / "dist",
))

if STATIC_DIR.is_dir():
    # attach subapplication at a path
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="frontend")