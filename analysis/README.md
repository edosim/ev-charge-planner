# Carbon savings analysis: how much CO₂ would have EV Charge Planner saved?


Over September 2026, scheduling a 28 kWh charge at 7 kW between 19:00 and 07:00 (UK time) in continuous mode would have cut emissions by 25%: 0.95 kg CO₂ per charge, or 28.5 kg over the month.

## Question

How much CO₂ does scheduling an overnight charge save, compared with charging as soon as the EV is plugged?


## Data

- **Source:** [Carbon Intensity API](https://carbonintensity.org.uk/), national endpoint `/intensity/{from}/{to}`
- **Period:** 01/09/2026 to 01/10/2026 (30 days, half-hourly)
- **Fields used:** `forecast` (to plan charge) and `actual` (to measure emissions)
- **Licence:** data by the National Energy System Operator (NESO), licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)


## The set-up

This analysis simulates an EV that is plugged in every night at 19:00 and must be charged by 07:00 the next morning (UK time). The EV needs 28 kWh every night and power is delivered constantly at 7 kW. This takes exactly 4 hours (or 8 half-hour slots), so no slot is only partially used.

Three scenarios were compared:

- Charge immediately: start at 19:00 and charge during the first 8 slots.
- Discrete mode: charge during the 8 greenest slots.
- Continuous mode: charge during the greenest 8-slot block.

The plans were made with the app's `plan_charge` function using the forecast intensity. The emissions for every plan were then calculated with the actual intensity.

## Results




| Mode        | Average emission per charge (kg)  | Average saving per charge (kg)|
| ----------- | -----------                       | ----------                    |
| Charge now  | 3.80                              |                               |
| Discrete    | 2.90                              | 0.89 (23%)                         |
| Continuous  | 2.84                              | 0.95 (25%)                        |


Smart charging cut emissions by a quarter.

Surprisingly, continuous charging saved slightly more than discrete charging. This is due to the difference between the forecast and the actual carbon intensity. Since over the month the difference was only about 0.06 kg per charge, both models are expected to perform similarly.

## Limitations

- **Average and marginal emissions:** the Carbon Intensity API reports the predicted average carbon intensity of the grid. However, a more relevant quantity would be the marginal carbon intensity which describes where extra energy to match demand would come from. Therefore, real-world savings could be different.
- **National carbon intensity:** the study uses the national average; local intensity varies.
- **Forecast error:** plans use forecasts, so some savings are lost when forecasts are wrong (actual emissions were 9% and 14% higher for the continuous and discrete modes, respectively).
- **Simplified charging:** constant power across all slots (even if the EV finishes before the final slot ends), no battery losses, same plug-in time every day.

## Reproduce

To reproduce this file, `savings_analysis` only needs the backend packages. From the top-level folder


```bash
pip install -r backend/requirements.txt
python analysis/savings_study.py
```

The script imports the planner from backend/main.py, so it measures the same code the app runs. It downloads the September 2026 data from the Carbon Intensity API, so it needs an internet connection.

## Files

`savings_analysis.py` downloads the data and runs the analysis.