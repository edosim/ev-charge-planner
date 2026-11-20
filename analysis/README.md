# Carbon savings analysis: how much CO₂ would EV Charge Planner have saved?


Over September 2026, scheduling a 28 kWh charge at 7 kW between 19:00 and 07:00 (UK time) in continuous mode would have cut emissions by 25%: 0.95 kg CO₂ per charge, or 28.5 kg over the month.

## Question

How much CO₂ does scheduling an overnight charge save, compared with charging as soon as the EV is plugged in?


## Data

- **Source:** [Carbon Intensity API](https://carbonintensity.org.uk/), national endpoint `/intensity/{from}/{to}`
- **Period:** 01/09/2026 to 01/10/2026 (30 days, half-hourly)
- **Fields used:** `forecast` (to plan charge) and `actual` (to measure emissions)
- **Licence:** data by the National Energy System Operator (NESO), licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)


## The set-up

This analysis simulates an EV that is plugged in every night at 19:00 and must be charged by 07:00 the next morning (UK time). The EV needs 28 kWh every night and power is delivered constantly at 7 kW. This takes exactly 4 hours (or 8 half-hour slots).

Three scenarios were compared:

- Charge immediately: start at 19:00 and charge during the first 8 slots.
- Discrete mode: charge during the 8 greenest slots.
- Continuous mode: charge during the greenest 8-slot block.

The plans were made with the app's `plan_charge` function using the forecast intensity. The emissions for every plan were then calculated with the actual intensity.

## Results




| Mode        | Average emissions per charge (kg)  | Average saving per charge (kg)|
| ----------- | -----------                       | ----------                    |
| Charge now  | 3.80                              |                               |
| Discrete    | 2.90                              | 0.89 (23%)                         |
| Continuous  | 2.84                              | 0.95 (25%)                        |


Smart charging cut emissions by a quarter.

Surprisingly, continuous charging saved slightly more than discrete charging. This is due to the difference between the forecast and the actual carbon intensity. Since over the month the difference was only about 0.06 kg per charge, both modes are expected to perform similarly.

## Limitations

- **Average and marginal emissions:** the Carbon Intensity API reports the predicted average carbon intensity of the grid. However, a more relevant quantity would be the marginal carbon intensity which describes where extra energy to match demand would come from.
- **Historical forecasts are final values:** the API does not keep forecast history. As each slot's forecast is updated, the earlier version is overwritten ([source](https://github.com/nmpowell/carbon-intensity-forecast-tracking)). The historical forecast is thus the latest version and likely more accurate than the one available at 19:00.
- **National carbon intensity:** the study uses the national average, but local intensity varies.
- **Forecast error:** plans use forecasts, so some savings are lost when forecasts are wrong (actual emissions were 9% and 14% higher for the continuous and discrete modes, respectively).
- **Simplified charging:** constant power across all slots, no battery losses, same plug-in time every day. Nights with a missing forecast or actual value are skipped and listed when the script runs (September 2026 had no skipped nights).

## Reproduce

To reproduce these results, `savings_analysis.py` only needs the backend packages. From the top-level folder:


```bash
pip install -r backend/requirements.txt
python analysis/savings_analysis.py
```

The script imports the planner from `backend/planner.py`, so it measures the same code the app runs. It downloads the September 2026 data from the Carbon Intensity API, so it needs an internet connection. 

The analysis tests run with the backend tests: `cd backend && mypy && pytest`.

## Files

- `savings_analysis.py` downloads the data and runs the analysis.
- `tests/test_analysis.py` tests the date chunking and the missing-data helper.