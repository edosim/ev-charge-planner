# Design decisions

The reasoning behind the main choices in EV Charge Planner. The [README](../README.md) has the short version.

## Planning

- **Two scheduling modes.** Discrete mode sorts the half-hours by forecast intensity and picks the greenest ones. Continuous mode finds the greenest unbroken block with a sliding window. It exists because some cars and chargers may handle stop-start schedules badly.
- **Constant AC charging.** The planner assumes home AC charging, up to 22 kW, at constant power. This is a fair model for AC: the car's onboard charger is the limit, so power stays flat until the battery is nearly full. DC fast charging tapers heavily, but nobody schedules a rapid charge across a 48-hour window.
- **The last half-hour may be partial.** Full half-hours count at full power; the last one counts only the energy still needed, because the car stops drawing power when it reaches its target. Putting the partial half-hour in the dirtiest chosen slot would be optimal on paper, but the slot would have to be cut down to an exact number of minutes. That number is worked out from the kWh the user entered, which is an estimate, so if the car needed slightly more it wouldn’t be full by the deadline. Scheduling whole half-hours and letting the car stop itself keeps the unused minutes of the last half-hour as a buffer.
- **Plans start at the next half-hour.** The half-hour in progress is never used, so a slot that's already partly over can't be counted as a full one. A deadline that falls before the first usable half-hour ends returns "Deadline is too soon". The "charge now" comparison also starts at the next half-hour, so both sides are measured the same way.
- **Not enough time.** If the deadline is too close for a full charge, the plan uses every available half-hour and reports a warning with how much charge will be delivered.
- **A minimum charge.** The number of half-hours is rounded to 6 decimal places before rounding up, to remove floating-point noise. That rounding would turn very small charges into plans with no slots, so charges below 0.00001 kWh are rejected. The minimum only works together with the 22 kW power limit, so a test checks the smallest charge at the highest power still needs one half-hour.

## Data and validation

- **Domain models.** Pydantic models guarantee the planner only receives valid data. Forecast slots must be timezone-aware, 30 minutes long and consecutive, which the scheduling and emissions code rely on. A user's request becomes a `ChargeRequest`: a validated, immutable object holding the charge, power, deadline and mode, which also works out how many half-hours the charge needs.
- **Validation at both entry points.** The endpoint's query limits reject bad requests before any forecast is fetched, and return a 422. `ChargeRequest` enforces the same limits for code that uses the planner directly, such as the savings analysis. Both read `backend/constants.py`.
- **Checks that depend on the time live in the endpoint.** Checks like "the deadline is in the future" depend on the current time and the forecast, so they're in the endpoint rather than the models. This keeps historical requests valid in the savings analysis.
- **Unused fields aren't checked.** Validation rejects bad values in fields the planner uses, but not in fields it ignores, such as the intensity `index`. With a strict check, one unexpected value in the shared national forecast would make every request fail.
- **Missing forecast values.** If a forecast value is missing, the app uses only the unbroken run of slots before it, so continuous mode never spans a gap.
- **Errors.** Bad input returns 422 with a message; a failing or malformed upstream response returns 503. The frontend turns FastAPI's validation errors into messages that name the form field, and handles error responses that aren't JSON.

## Time

- **UK in, UTC inside.** The deadline is entered in UK time and converted to UTC once. Everything else works in UTC, and UK time is used again only for display.
- **Clock changes.** A time that doesn't exist when the clocks go forward (for example 01:30 on the last Sunday of March) is rejected rather than silently moved. A time that happens twice when the clocks go back means the first one, the earlier and safer deadline.
- **No time zones on input.** A deadline time sent with a time zone is rejected, because it would otherwise be silently read as UK time.

## Testing

- **Injected client and clock.** One shared `httpx.AsyncClient` is created at startup, and the current time comes from a `get_now` dependency. Tests replace both: the client with a fake Carbon Intensity API (`httpx.MockTransport`), and the clock with a fixed time, so results don't depend on when the tests run.
- **A winter test date.** The fixed test time is in late October, after the clocks go back, so UK time equals UTC and test deadlines line up with the fake forecast.
- **Logic outside components.** Frontend logic such as grouping charging times, chart labels and error messages lives in plain functions (`plan.ts`, `errors.ts`), tested without rendering the page.
- **Not yet tested.** React components are currently untested. Only the plain functions they use are tested.

## Frontend and deployment

- **Matching types.** TypeScript types mirror the Pydantic response models.
- **Shared limits.** The form's limits live in `frontend/src/limits.ts`. The backend remains the real check, and a backend test checks the two maximums match `constants.py`.
- **One container.** FastAPI serves both the API and the built React page and the page and API share an origin.
- **Docker image.** A multi-stage build ships only Python and the built page, and runs as a non-root user.
- **Cloud Run.** The service runs as an account with no permissions, scales to zero, is capped at one instance, and has a spend cap.