import asyncio
import httpx

from datetime import datetime, timezone, timedelta
from main import Slot, fetch_forecast, plan_charge,ChargeRequest

from pydantic import (
    BaseModel,
    Field,
    AwareDatetime,
    field_validator,
    model_validator,
    ConfigDict,
)

from typing import Self

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


PRODUCT_CODE = "AGILE-24-10-01"
TARIFF_CODE = "E-1R-AGILE-24-10-01-C"
BASE_URL = "https://api.octopus.energy/v1/products"

endpoint = BASE_URL + f"/{PRODUCT_CODE}/electricity-tariffs/{TARIFF_CODE}/standard-unit-rates/"

now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
params = {
    "period_from": now
}


async def fetch_prices(client: httpx.AsyncClient, params):

    resp = await client.get(endpoint, params=params,timeout=10)
    resp.raise_for_status()
    return PricesResponse.model_validate(resp.json())


def plan_price(prices: list[Price], slots: list[Slot]) -> list[Price]:
    """Return prices of slots"""
    slots_starts = [s.start for s in slots]
    prices_chosen = [r for r in prices if r.start in slots_starts]

    return sorted(prices_chosen, key=lambda p: p.start)

async def main():
    #get prices
    async with httpx.AsyncClient() as client:
        response = await fetch_prices(client, params)

    print(response.count, response.next, response.previous)

    #get carbon intensity slots
    async with httpx.AsyncClient() as client:
        slots = await fetch_forecast(client)

    deadline = datetime.now(timezone.utc) + timedelta(hours=10)
    request_input = {
        "charge_needed_kwh": 16,
        "charge_rate_kw": 7,
        "deadline": deadline,
        "mode": "discrete",
    }
    request = ChargeRequest.model_validate(request_input)
    plan, _ = plan_charge(slots, request)

    for s in plan:
        print(s.start.time())
    plan_prices = plan_price(response.prices, plan)
    for p in plan_prices:
        print(p.start.time())

asyncio.run(main())




