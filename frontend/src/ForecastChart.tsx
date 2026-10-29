// chart components
import { Bar, BarChart, CartesianGrid, Rectangle, Tooltip, XAxis, YAxis, type BarShapeProps } from 'recharts'
import type { Slot } from './types'
import { formatUk } from './time'

type Props = {
  forecast: Slot[]
  chosen: Slot[]
}

const CHOSEN_COLOUR = '#2e9d5b'
const OTHER_COLOUR = '#c4c9cf'

export default function ForecastChart({ forecast, chosen }: Props) {
  // like {s.start for s in chosen}
  const chosenStarts = new Set(chosen.map((slot) => slot.from))

  // object with time of forecast, intensity of forecast and the times of the chosen slots 
  const data = forecast.map((slot) => ({
    time: formatUk(slot.from),
    intensity: slot.intensity.forecast,
    chosen: chosenStarts.has(slot.from),
  }))

  return (
    //pass table to chart, responsive (chart refits to container), style (full width 320px height)
    <BarChart data={data} responsive style={{ width: '100%', height: 320 }}>
      {/* add horizontal grid lines. 3 px of line 3 of gap*/} 
      <CartesianGrid vertical={false} strokeDasharray="3 3" />
      {/*read column time of data as x, skip 7 labels (i.e., 1 every 8(4h)). Wed 07:00 becomes 07:00 */}
      <XAxis dataKey="time" interval={7} tickFormatter={(time: string) => time.split(' ')[1]} />
      {/*nothing on the y axis. get scale from data*/}
      <YAxis />
      {/*show x and y when hovering*/}
      <Tooltip />
      <Bar
        dataKey="intensity"
        name="Forecast (gCO₂/kWh)"
        // turn off growing in animation
        // isAnimationActive={false}
        // function to colour in chosen slots and other slots
        //take props of type BarShapeProps and return a rectangle with props with fill value replaced
        shape={(props: BarShapeProps) => (
          <Rectangle {...props} fill={data[props.index].chosen ? CHOSEN_COLOUR : OTHER_COLOUR} />
        )}
      />
    </BarChart>
  )
}