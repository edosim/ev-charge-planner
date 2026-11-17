import httpx
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
from main import ForecastResponse, plan_charge, ChargeRequest, BASE_URL, Slot
from constants import UK

CHARGE_NEEDED = 28 #kWh
CHARGE_RATE = 7 #kW

# Here input the first and last dates of the time period you want to calculate
# carbon savings for
START_DATE = "2026-09-01"
END_DATE = "2026-10-01" 
# Only calculated for charging between 7pm and 7am
# (during clock changes it uses the local 7pm and 7am to reflect people's behaviour)


def fetch_forecast(start: str, end: str) -> list[Slot]:
    resp = httpx.get(f"{BASE_URL}/intensity/{start}/{end}", timeout=10)
    resp.raise_for_status()
    slots = ForecastResponse.model_validate(resp.json()).data
    return slots

def split_dates_by_num_days(start_date: datetime, end_date: datetime, num_days: int = 14,
                            ) -> list[tuple[str, str]]:
    """Split dates in chunks of `num_days` days 23 hours, 59 minutes,
    skipping one minute in between (12:01 - 12:00).
    Used for fetching forecast in `num_days` (14) days chunks."""

    # change time to midday
    start_date = start_date.replace(hour=12, minute=1, tzinfo=timezone.utc)
    end_date = end_date.replace(hour=12, minute=0, tzinfo=timezone.utc)

    dates_to_fetch = []
    start_period = start_date
    end_period = start_period + timedelta(days=num_days-1, hours=23, minutes=59)

    while end_period < end_date:
        dates_to_fetch.append((start_period.strftime('%Y-%m-%dT%H:%M:%SZ'), end_period.strftime('%Y-%m-%dT%H:%M:%SZ')))
        
        start_period = start_period + timedelta(days=num_days)
        end_period = start_period + timedelta(days=num_days-1, hours=23, minutes=59)

    dates_to_fetch.append((start_period.strftime('%Y-%m-%dT%H:%M:%SZ'), end_date.strftime('%Y-%m-%dT%H:%M:%SZ')))
    return dates_to_fetch

def all_present(values: list[int | None]) -> list[int] | None:
    """Check that no None is presen in forecasts or actuals to be used in the savings"""
    present = [v for v in values if v is not None]
    return present if len(present) == len(values) else None

def main(start: str, end: str) -> None:

    #turn into datetime objects
    start_date = datetime.strptime(start, "%Y-%m-%d")
    end_date = datetime.strptime(start, "%Y-%m-%d")

    dates_to_fetch = split_dates_by_num_days(start_date, end_date, 14)

    # Fetch slots
    slots = []
    for start, end in dates_to_fetch:
        slots += fetch_forecast(start, end)

    total_days = (end_date - start_date).total_seconds() / 86400
    print(f"Carbon saved between {start_date.strftime('%d/%m/%Y')} and {end_date.strftime('%d/%m/%Y')} "
            f"({total_days} days) compared to charging immediately.")

    for mode in ('discrete', 'continuous'):
        forecasts = []
        actuals = []
        dates_skipped = []
        charge_nows = []
        date_utc = start_date
        while date_utc < end_date:

            date_uk = date_utc.replace(hour=19, minute=0, tzinfo=UK)
            # this adds 12 hours naively, i.e. always at 7am the next day even on clock
            # change days (which is what we want)
            deadline = date_uk + timedelta(hours=12)
            
            slots_of_date = [s for s in slots if s.start >= date_uk and s.end <= date_uk + timedelta(hours=48)]
     
            request_input = {
                "charge_needed_kwh": CHARGE_NEEDED,
                "charge_rate_kw": CHARGE_RATE,
                "deadline": deadline,
                "mode": mode,
            }
            request = ChargeRequest.model_validate(request_input)

            chosen, _ = plan_charge(slots_of_date, request)

            forecasts_current = all_present([s.intensity.forecast for s in chosen])
            actuals_current = all_present([s.intensity.actual for s in chosen])
            charge_now_current = all_present([s.intensity.actual for s in slots_of_date[:len(chosen)]])
            
            # If any forecast or actual is None skip that night
            if forecasts_current is None or actuals_current is None or charge_now_current is None:
                dates_skipped.append(date_uk)
            else:
                forecasts.append(sum(forecasts_current))
                actuals.append(sum(actuals_current))
                charge_nows.append(sum(charge_now_current))

            date_utc += timedelta(days=1)


        forecasts_total = sum(forecasts) * CHARGE_RATE / 2 / 1000
        actuals_total = sum(actuals) * CHARGE_RATE / 2 / 1000
        charge_nows_total = sum(charge_nows) * CHARGE_RATE / 2 / 1000

        predicted_savings: float = sum([n - i for (n, i) in zip(charge_nows, forecasts)])
        predicted_savings *= CHARGE_RATE / 2 / 1000
        actual_savings: float = sum([n - i for (n, i) in zip(charge_nows, actuals)])
        actual_savings *= CHARGE_RATE / 2 / 1000

        print()
        print(f"---- {mode.capitalize()} mode ----")
        print(f"Predicted emissions: {forecasts_total:.3f} kg ({forecasts_total/total_days:.3f} kg/day)")
        print(f"Actual emissions: {actuals_total:.3f} kg ({actuals_total/total_days:.3f} kg/day)")
        print(f"'Charge now' emissions: {charge_nows_total:.3f} kg ({charge_nows_total/total_days:.3f} kg/day)")
        print()
        print(f"Predicted savings: {predicted_savings:.3f} kg ({predicted_savings/total_days:.3f} kg/day)")
        print(f"Actual savings: {actual_savings:.3f} kg ({actual_savings/total_days:.3f} kg/day)")

if __name__ == "__main__":
    main(START_DATE, END_DATE)