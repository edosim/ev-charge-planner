import asyncio
import httpx

from datetime import datetime, timezone, timedelta

from schemas import PricesResponse, Price, Slot, ChargeRequest, SLOT_HOURS



PRODUCT_CODE = "AGILE-24-10-01"
TARIFF_CODE = "E-1R-AGILE-24-10-01-C" # C at the end is london for now
BASE_URL = "https://api.octopus.energy/v1/products"

ENDPOINT = BASE_URL + f"/{PRODUCT_CODE}/electricity-tariffs/{TARIFF_CODE}/standard-unit-rates/"



async def fetch_prices(client: httpx.AsyncClient) -> PricesResponse:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
    resp = await client.get(ENDPOINT, params={"period_from": now},timeout=10)
    resp.raise_for_status()
    return PricesResponse.model_validate(resp.json())


def get_total_price(prices: list[Price], slots: list[Slot], charge_rate_kw: float) -> float | None:
    """Return total price of slots if available for all slots. Otherwise, `None`"""
    slots_start = {s.start for s in slots}
    prices_chosen = [r for r in prices if r.start in slots_start]

    if len(prices_chosen) != len(slots):
        return None
    return sum(p.value_inc_vat for p in prices_chosen) * SLOT_HOURS * charge_rate_kw

async def main() -> None:
    from main import fetch_forecast, plan_charge

    #get prices
    async with httpx.AsyncClient() as client:
        response = await fetch_prices(client)
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
    price_total = get_total_price(prices, plan, request.charge_rate_kw)
    if price_total is not None:
        print(f"£{price_total/100:.2f}")
    else:
        print("Prices are not available for all slots.")

if __name__ == "__main__":
    asyncio.run(main())




