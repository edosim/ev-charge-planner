from pydantic import (
    BaseModel,
    Field,
    AwareDatetime,
    field_validator,
    model_validator,
    ConfigDict,
)
from datetime import datetime, timezone, timedelta
from typing import Self, Literal
import math #for ceil

from constants import (
    MAX_CHARGE_KWH, MIN_CHARGE_KWH,
    MAX_CHARGE_RATE_KW, MIN_CHARGE_RATE_KW,
)



# Carbon Intensity API models
class Intensity(BaseModel):
    model_config = ConfigDict(frozen=True)

    forecast: int | None = Field(ge=0)
    actual: int | None = None
    index: Literal["very low", "low", "moderate", "high", "very high"]


class Slot(BaseModel):
    model_config = ConfigDict(frozen=True)

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
    
    @property
    def forecast(self) -> int:
        """Forecast intensity. Only call this on slots known to have a forecast."""
        if self.intensity.forecast is None:
            raise ValueError(f"Slot starting {self.start} has no forecast")
        return self.intensity.forecast
    
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

    charge_needed_kwh: float = Field(gt=MIN_CHARGE_KWH, le=MAX_CHARGE_KWH)
    charge_rate_kw: float = Field(gt=MIN_CHARGE_RATE_KW, le=MAX_CHARGE_RATE_KW)
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


# Endpoint

class ScheduleResponse(BaseModel):
    slots: list[Slot]
    forecast: list[Slot]
    emissions_kg: float
    charge_now_kg: float
    saved_kg: float
    fully_charged: bool




