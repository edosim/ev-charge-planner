"""Test that constants in front end are the same as in the backend"""

from pathlib import Path
import re

from constants import (
    MAX_CHARGE_KWH, MAX_CHARGE_RATE_KW,
)

constants = {
    "MAX_CHARGE_KWH": MAX_CHARGE_KWH,
    "MAX_CHARGE_RATE_KW": MAX_CHARGE_RATE_KW,
}

LIMITS_TS_PATH = Path(__file__).resolve().parents[2] / "frontend" / "src" / "limits.ts"

def get_frontend_constant(name: str) -> float:
    match = re.search(rf"export const {name} = ([\d.]+)",LIMITS_TS_PATH.read_text(encoding="utf-8"))
    assert match, f"{name} not found in limits.ts"
    return float(match.group(1))

def test_constants_match():
    for name, value in constants.items():
        assert value == get_frontend_constant(name)