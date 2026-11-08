"""Test for fetch_prices, using a fake HTTP client

using httpx.MockTransport"""

import pytest

import asyncio
import httpx
from datetime import datetime, timezone, timedelta
from pydantic import ValidationError

from prices import fetch_prices, TARIFF_CODE, PRODUCT_CODE


TEST_RESPONSE = {
    "count": 3,
    "next": None,
    "previous": None,
    "results": [
        {
        "value_exc_vat": 41.94,
        "value_inc_vat": 41.94,
        "valid_from": "2026-11-06T22:30:00Z",
        "valid_to": "2026-11-06T23:00:00Z",
        "payment_method": None
        },
        {
        "value_exc_vat": 42.91,
        "value_inc_vat": 42.91,
        "valid_from": "2026-11-06T22:00:00Z",
        "valid_to": "2026-11-06T22:30:00Z",
        "payment_method": None
        },
        {
        "value_exc_vat": 44.17,
        "value_inc_vat": 44.17,
        "valid_from": "2026-11-06T21:30:00Z",
        "valid_to": "2026-11-06T22:00:00Z",
        "payment_method": None
        },
    ]
}

# Response missing values
BAD_SHAPE_RESPONSE = {
    "count": 3,
    "next": None,
    "previous": None,
    "results": [{"value_exc_vat": 41.94},]
}



def fetch_with(handler):
    """Run fetch with a fake server"""
    async def run():
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            return await fetch_prices(client)
    return asyncio.run(run())

def test_parses_response():
    response = fetch_with(lambda request: httpx.Response(200, json=TEST_RESPONSE)) 

    assert len(response.prices) == 3
    assert response.count == 3
    assert [p.value_exc_vat for p in response.prices] == [44.17, 42.91, 41.94]
    assert response.prices[0].start == datetime(2026, 11, 6, 21, 30, tzinfo=timezone.utc)
    assert response.prices[0].end == datetime(2026, 11, 6, 22, 00, tzinfo=timezone.utc)

def test_calls_the_agile_endpoint():
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json = TEST_RESPONSE)

    fetch_with(handler)

    assert len(seen) == 1
    path = seen[0].url.path
    host = seen[0].url.host
    assert path == (f"/v1/products/{PRODUCT_CODE}/electricity-tariffs/"
                    f"{TARIFF_CODE}/standard-unit-rates/")
    assert host == "api.octopus.energy"

def test_server_error_raises():
    with pytest.raises(httpx.HTTPStatusError):
        fetch_with(lambda request: httpx.Response(500))

def test_unexpected_shape_raises():
    with pytest.raises(ValidationError):
        fetch_with(lambda request: httpx.Response(200, json=BAD_SHAPE_RESPONSE))

def test_requests_prices_from_now():
    seen = []
    def handler(request):
        seen.append(request)
        return httpx.Response(200, json=TEST_RESPONSE)
    fetch_with(handler)

    period_from = datetime.fromisoformat(seen[0].url.params["period_from"])
    assert abs(period_from - datetime.now(timezone.utc)) < timedelta(minutes=2)