import asyncio
import httpx

from datetime import datetime, timezone, timedelta
from typing import Any

from main import fetch_forecast, plan_charge
from schemas import PricesResponse, Price, Slot, ChargeRequest



PRODUCT_CODE = "AGILE-24-10-01"
TARIFF_CODE = "E-1R-AGILE-24-10-01-C" # C at the end is london for now
BASE_URL = "https://api.octopus.energy/v1/products"

endpoint = BASE_URL + f"/{PRODUCT_CODE}/electricity-tariffs/{TARIFF_CODE}/standard-unit-rates/"

now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
params = {
    "period_from": now
}


async def fetch_prices(client: httpx.AsyncClient, params: dict[str, Any]) -> PricesResponse:

    resp = await client.get(endpoint, params=params,timeout=10)
    resp.raise_for_status()
    return PricesResponse.model_validate(resp.json())


def plan_price(prices: list[Price], slots: list[Slot]) -> list[Price]:
    """Return prices of slots"""
    slots_starts = [s.start for s in slots]
    prices_chosen = [r for r in prices if r.start in slots_starts]

    return sorted(prices_chosen, key=lambda p: p.start)

async def main() -> None:
    #get prices
    async with httpx.AsyncClient() as client:
        response = await fetch_prices(client, params)
    prices = response.prices
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
    plan_prices = plan_price(prices, plan)
    for p in plan_prices:
        print(p.start.time())

if __name__ == "__main__":
    asyncio.run(main())




