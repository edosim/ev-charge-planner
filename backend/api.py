from contextlib import asynccontextmanager
from datetime import datetime, time, timedelta, date, timezone
from typing import Literal
from constants import (
    MAX_CHARGE_KWH, MIN_CHARGE_KWH,
    MAX_CHARGE_RATE_KW, MIN_CHARGE_RATE_KW,
    DEFAULT_CHARGE_RATE_KW,
    UK,
)

import httpx
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from pydantic import ValidationError
import json
from collections.abc import AsyncGenerator

from schemas import Slot, ChargeRequest, ScheduleResponse
from planner import emissions_kg, fetch_forecast, plan_charge

import os
from pathlib import Path

from fastapi.staticfiles import StaticFiles




@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    async with httpx.AsyncClient() as client:
        app.state.client = client      # created once when the server starts
        yield                          # the server runs here
    # client closed automatically when the server stops


app = FastAPI(title="EV Charge Planner", lifespan=lifespan)

def get_client(request: Request) -> httpx.AsyncClient:
      client: httpx.AsyncClient = request.app.state.client
      return client

def get_now() -> datetime:
    """Get current time in UTC. A dependency so planner and endpoint share the same
    time and tests can pin the clock."""
    return datetime.now(timezone.utc)


def check_deadline(deadline: datetime, slots: list[Slot],
                   now: datetime | None = None) -> None:
    """Check that the deadline is in the data from the Carbon Intensity API,
    and after now."""
    if now is None:
        now = datetime.now(timezone.utc)
    if deadline <= now:
        raise ValueError("Deadline must be in the future.")
    if deadline > slots[-1].end:
        raise ValueError("Deadline must be within the next 48h "
                         f"(before {slots[-1].end.astimezone(UK):%a %H:%M}).")

def uk_deadline(date_deadline: date, time_deadline: time) -> datetime:
    """Combines UK date and time into UTC deadline"""
    return datetime.combine(date_deadline, time_deadline, tzinfo=UK)
    
# the endpoint
@app.get("/schedule", response_model=ScheduleResponse)
async def schedule(
    charge_needed_kwh: float = Query(gt=MIN_CHARGE_KWH, le=MAX_CHARGE_KWH, description="Energy needed for car in kWh"),
    deadline_date: date = Query(description="Date when the car should finish charging, UK time, e.g. 2026-10-25"),
    deadline_time: time = Query(description="Time when the car should finish charging, UK time, e.g. 07:00"),
    charge_rate_kw: float = Query(DEFAULT_CHARGE_RATE_KW, gt=MIN_CHARGE_RATE_KW, le=MAX_CHARGE_RATE_KW, description="Charge power in kW"),
    mode: Literal["discrete","continuous"] = "discrete",
    client: httpx.AsyncClient = Depends(get_client),
    now: datetime = Depends(get_now),
) -> ScheduleResponse:
    
    try:
        slots = await fetch_forecast(client, now)
    except (httpx.HTTPError, ValidationError, json.JSONDecodeError):
        raise HTTPException(status_code=503, detail="Carbon Intensity API is unavailable")

    if not slots:
        raise HTTPException(status_code=503, detail="No forecast data available")         
                       
    deadline = uk_deadline(deadline_date, deadline_time)
    request = ChargeRequest(
         charge_needed_kwh = charge_needed_kwh,
         charge_rate_kw = charge_rate_kw,
         deadline = deadline,
         mode = mode
    )

    try:
        check_deadline(request.deadline, slots, now)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    #Get best slots
    plan, charge_delivered_kwh, fully_charged = plan_charge(slots, request)
    #Get emissions
    smart_kg = emissions_kg(plan, request)
    now_kg = emissions_kg(slots[:len(plan)], request)
    saved_kg = now_kg - smart_kg

    return ScheduleResponse(slots=plan,
                            forecast=slots,
                            emissions_kg=round(smart_kg,3),
                            charge_now_kg=round(now_kg,3),
                            saved_kg=round(saved_kg, 3), #same precision as two above
                            charge_delivered_kwh=charge_delivered_kwh, 
                            fully_charged=fully_charged
    )


# Serve the built React page. Must come at the end of file

#get path of distribution of front end
STATIC_DIR = Path(os.environ.get(
    "STATIC_DIR",
    Path(__file__).resolve().parent.parent / "frontend" / "dist",
))

def mount_app(app: FastAPI, static_dir: Path) -> None:

    if static_dir.is_dir():
    # attach subapplication at a path
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="frontend")

mount_app(app, STATIC_DIR)