import { useState } from 'react'
import type { ScheduleResponse, Slot } from './types'
import { formatUk } from './time'
import ForecastChart from './ForecastChart'

// create type for the two modes
type Mode = 'discrete' | 'continuous'

// make helper function with text for output
function describePlan(slots: Slot[]): string {
  const count = slots.length
  const hours = count / 2
  const slotWord = count === 1 ? 'slot' : 'slots'
  const hourWord = hours === 1 ? 'hour' : 'hours'
  return `Charging during ${count} half-hour ${slotWord} (${hours} ${hourWord}).`
}


function App() {
  // Creates place to write input(default), with its name and the function allowed to change it
  // equivalent to python's unpacking: a, b = ...
  const [chargeNeeded, setChargeNeeded] = useState('20')
  const [deadlineDate, setDeadlineDate] = useState('')
  const [deadlineTime, setDeadlineTime] = useState('07:00')
  const [chargeRate, setChargeRate] = useState('7')
  // <> tell it what it can hold
  const [mode, setMode] = useState<Mode>('discrete')

  const [result, setResult] = useState<ScheduleResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  // calling the API
  async function handleSubmit() {
    setLoading(true)
    setError(null)
    setResult(null)

    // query params
    const params = new URLSearchParams({
      charge_needed_kwh: chargeNeeded,
      deadline_date: deadlineDate,
      deadline_time: deadlineTime,
      charge_rate_kw: chargeRate,
      mode,
    })

    try {
      // await client.get(..). `${}` are like f"{}"
      const response = await fetch(`/schedule?${params}`)
      const body = await response.json()
      // if not response.ok
      if (!response.ok) {
        // cond ? a : b same as a if cond else b
        // aka deyail if type(detail) == str else json.dumps(detail)
        setError(typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail))
        return
      }
      setResult(body)
    } catch (err) { //except
      //write error to browser's developer console
      console.error(err)
      setError('Could not reach the server.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <main>
      <h1>GreenCharge</h1>
      <p className='tagline'>Plan your EV charge for the UK's greenest half-hours</p>

      {/* when button is pressed or enter in a field is pressed
      => like lambda*/}
      <form
        onSubmit={(event) => {
          {/* Prevents reloading all page */}
          event.preventDefault()
          handleSubmit()
        }}
      >
        <label>
          Charge needed (kWh)
          <input
            type="number"
            min="0.5"
            step="0.5"
            value={chargeNeeded}
            onChange={(e) => setChargeNeeded(e.target.value)}
            required
          />
        </label>

        <label>
          Charger power (kW)
          <input
            type="number"
            min="1"
            step="0.1"
            value={chargeRate}
            onChange={(e) => setChargeRate(e.target.value)}
            required
          />
        </label>

        <label>
          Ready by (date)
          <input
            type="date"
            value={deadlineDate}
            onChange={(e) => setDeadlineDate(e.target.value)}
            required
          />
        </label>

        <label>
          Ready by (time, UK)
          <input
            type="time"
            value={deadlineTime}
            onChange={(e) => setDeadlineTime(e.target.value)}
            required
          />
        </label>

        <label>
          Mode
          <select value={mode} onChange={(e) => setMode(e.target.value as Mode)}>
            <option value="discrete">Greenest slots</option>
            <option value="continuous">One unbroken block</option>
          </select>
        </label>

        <button type="submit" disabled={loading}>
          {loading ? 'Planning…' : 'Plan my charge'}
        </button>
      </form>

      {error && (
        <p className="error" role="alert">
          Error: {error}
          </p>
        )}

      {result && (
        <section className='results'>
          <div className="stats">
            <div className="stat">
             <span className='stat-value'>{result.emissions_kg} kg</span>
             <span className='stat-label'>CO₂ with this plan</span>
            </div>
            <div className="stat">
             <span className='stat-value'>{result.charge_now_kg} kg</span>
             <span className='stat-label'>CO₂ if you charged now</span>
            </div>
            <div className="stat">
             <span className='stat-value'>{result.saved_kg} kg</span>
             <span className='stat-label'>CO₂ saved</span>
            </div>
          </div>
          <p className='summary'>{describePlan(result.slots)}</p>

            <ForecastChart forecast={result.forecast} chosen={result.slots} />

            <ul className='slot-list'>
            {result.slots.map((slot) => (
              <li key={slot.from}>
                {formatUk(slot.from)} – {formatUk(slot.to)}
              </li>
            ))}
          </ul>
        </section>
      )}
    </main>
  )
}

export default App