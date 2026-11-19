// chart components
import { Bar, BarChart, CartesianGrid, Rectangle, Tooltip, XAxis, YAxis, type BarShapeProps } from 'recharts'
import type { Slot } from './types'
import { formatUk } from './time'
import { chartTicks } from './plan'

type Props = {
  forecast: Slot[]
  chosen: Slot[]
}

const CHOSEN_COLOUR = '#2e9d5b'
const OTHER_COLOUR = '#c4c9cf'

export default function ForecastChart({ forecast, chosen }: Props) {
  // like {s.start for s in chosen}
  const chosenStarts = new Set(chosen.map((slot) => slot.from))

  // one row per slot, keyed by its start time
  const data = forecast.map((slot) => ({
    from: slot.from,
    intensity: slot.intensity.forecast,
    chosen: chosenStarts.has(slot.from),
  }))

  const { ticks, labels } = chartTicks(forecast)

  return (
    <div>
      {/*bull list HTML class named legend.*/}
      <ul className="legend">
        <li>
          <span className="swatch" style={{ background: CHOSEN_COLOUR }} aria-hidden="true" />
          Charging
        </li>
        <li>
          <span className="swatch" style={{ background: OTHER_COLOUR }} aria-hidden="true" />
          Not charging
        </li>
      </ul>
      {/*//pass table to chart, responsive (chart refits to container), style (full width 320px height)*/}
      <BarChart data={data} responsive style={{ width: '100%', height: 320 }}>
        {/* add horizontal grid lines. 3 px of line 3 of gap*/} 
        <CartesianGrid vertical={false} strokeDasharray="3 3" />
        {/* a tick every 4 hours; the first tick of each day shows the weekday */}
        <XAxis
          dataKey="from"
          ticks={ticks}
          interval={0}
          height={44}
          tick={({ x, y, payload }) => {
            const label = labels.get(payload.value)
            if (!label) return <g />
            return (
              <text x={x} y={y} textAnchor="middle" fill="#666">
                <tspan x={x} dy="0.71em">{label.time}</tspan>
                {label.day && <tspan x={x} dy="1.2em">{label.day}</tspan>}
              </text>
            )
          }}
        />
        {/*nothing on the y axis. get scale from data*/}
        <YAxis />
        {/* show the UK time and intensity when hovering */}
        <Tooltip labelFormatter={(value) => formatUk(String(value))} />
        <Bar
          dataKey="intensity"
          name="Forecast (gCO₂/kWh)"
          // turn off growing-in animation
          // isAnimationActive={false}
          // function to colour in chosen slots and other slots
          //take props of type BarShapeProps and return a rectangle with props with fill value replaced
          shape={(props: BarShapeProps) => (
            <Rectangle {...props} fill={data[props.index].chosen ? CHOSEN_COLOUR : OTHER_COLOUR} />
          )}
        />
      </BarChart>
  </div>
  )
}