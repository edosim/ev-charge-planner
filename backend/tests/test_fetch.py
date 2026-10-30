"""Test for fetch_forecast, using a fake HTTP client

using httpx.MockTransport"""

import pytest


import asyncio
import httpx
from datetime import datetime, timezone

from main import fetch_forecast

TEST_RESPONSE = {
    'data': [
        {"from": "2026-10-27T12:00Z", "to": "2026-10-27T12:30Z",
         "intensity": {"forecast": 50, "actual": None, "index": "moderate"}},
        {"from": "2026-10-27T12:30Z", "to": "2026-10-27T13:00Z",
         "intensity": {"forecast": 100, "actual": None, "index": "low"}},
        {"from": "2026-10-27T13:00Z", "to": "2026-10-27T13:30Z",
         "intensity": {"forecast": None, "actual": None, "index": "moderate"}},
    ]
}

def fetch_with(handler):
    """Run fetch with a fake server"""
    async def run():
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            return await fetch_forecast(client)
    return asyncio.run(run())

def test_parses_response_and_excludes_missing_forecasts():
    slots = fetch_with(lambda request: httpx.Response(200, json=TEST_RESPONSE))

    assert len(slots) == 2
    assert [s.intensity.forecast for s in slots] == [50, 100]
    assert slots[0].start == datetime(2026, 10, 27, 12, 0, tzinfo=timezone.utc)
    assert slots[0].end == datetime(2026, 10, 27, 12, 30, tzinfo=timezone.utc)
    assert slots[1].intensity.index == "low"

def test_calls_the_48h_forecast_endpoint():
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json={"data": []})

    fetch_with(handler)

    assert len(seen) == 1
    path = seen[0].url.path
    assert path.startswith("/intensity/")
    assert path.endswith("/fw48h")

def test_server_error_raises():
    with pytest.raises(httpx.HTTPStatusError):
        fetch_with(lambda request: httpx.Response(500))


def test_unexpected_shape_raises():
    from pydantic import ValidationError

    broken = {"data": [{"to": "2026-10-27T12:00Z"}]}       # missing "from" and "intensity"
    with pytest.raises(ValidationError):
        fetch_with(lambda request: httpx.Response(200, json=broken))
