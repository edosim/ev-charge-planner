from pydantic import (
    BaseModel,
    Field,
    AwareDatetime,
    field_validator,
    model_validator,
    ConfigDict,
)

from typing import Self, Literal
from datetime import datetime, timedelta, timezone
import math

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


# ------ Octous prices models

class Price(BaseModel):
    model_config = ConfigDict(frozen=True)

    value_exc_vat: float
    value_inc_vat: float
    start: AwareDatetime = Field(alias="valid_from")
    end: AwareDatetime = Field(alias="valid_to")
    payment_method: str | None

    @field_validator("start", "end")
    @classmethod
    def to_utc(cls, value: datetime) -> datetime:
        """Converts `start` and `end` fields to UTC"""
        return value.astimezone(timezone.utc)


class PricesResponse(BaseModel):
    count: int
    next: str | None
    previous: str | None
    prices: list[Price] = Field(alias="results")

    @model_validator(mode="after")
    def check_consecutive(self) -> Self:
        """Check that a slot end time is the same as the next's start time"""
        for previous, current in zip(self.prices[:-1],self.prices[1:]):
            if previous.end != current.start:
                raise ValueError("Slots must be consecutive. Found a gap after"
                                 f"{previous.end:%Y-%m-%d %H:%M} UTC")
        return self

