import { describe, expect, it } from 'vitest'
import type { Slot } from './types'
import { chartTicks, describePlan, groupSlots, formatKg } from './plan'

// make slots starting at 00:00 on 30/10/2026 or other date
// kinda bad. would be better to use Date objects
// but works for now
function makeSlots(count: number, day = "30"): Slot[] {
  const slots: Slot[] = []
  for (let i = 0; i < count; i++) {
    // get starting time
    let hours = Math.floor(i / 2);
    let minutes = i % 2 * 30;
    let hoursString = String(hours).padStart(2, '0');
    let minutesString = String(minutes).padStart(2, '0');
    const from = `2026-10-${day}T${hoursString}:${minutesString}:00Z`;
    // get ending time
    hours = Math.floor((i + 1) / 2);
    minutes = (i + 1) % 2 * 30;
    hoursString = String(hours).padStart(2, '0');
    minutesString = String(minutes).padStart(2, '0');
    const to = `2026-10-${day}T${hoursString}:${minutesString}:00Z`;

    slots.push({
      from,
      to,
      intensity: { forecast: 0, actual: null, index: 'low', }, //placeholder
    })
  }
  return slots
}



describe('describePlan', () => {
  it("uses singular 'slot' for one slot", () => {
    expect(describePlan(makeSlots(1))).toBe('Charging during 1 half-hour slot (0.5 hours).')
  })
  it("uses singular 'hour' for one hour", () => {
    expect(describePlan(makeSlots(2))).toBe('Charging during 2 half-hour slots (1 hour).')
  })
  it("uses plural for both in all other cases", () => {
    expect(describePlan(makeSlots(3))).toBe('Charging during 3 half-hour slots (1.5 hours).')
  })
})



describe('groupSlots', () => {
  it("returns one group if they are adjacent", () => {
    expect(groupSlots(makeSlots(4)).length).toBe(1)
  })
  it("returns each group's start and end", () => {
    const groups = groupSlots([...makeSlots(4), ...(makeSlots(4, "31"))]);
    expect(groups.map((g) => [g.from, g.to])).toEqual(
      [["2026-10-30T00:00:00Z", "2026-10-30T02:00:00Z"],
      ["2026-10-31T00:00:00Z", "2026-10-31T02:00:00Z"]])
  })
})

describe('chartTicks', () => {
  it('puts a tick every 4 hours and labels each new day', () => {
    const { ticks, labels } = chartTicks([...makeSlots(48), ...makeSlots(48, '31')])
    expect(ticks.map((t) => labels.get(t))).toEqual([
      { time: '00:00', day: 'Fri' }, { time: '04:00' }, { time: '08:00' },
      { time: '12:00' }, { time: '16:00' }, { time: '20:00' },
      { time: '00:00', day: 'Sat' }, { time: '04:00' }, { time: '08:00' },
      { time: '12:00' }, { time: '16:00' }, { time: '20:00' },
    ])
  })
  it('gives the first tick a weekday even when it is not midnight', () => {
    const { ticks, labels } = chartTicks(makeSlots(48).slice(10))   // starts at 05:00
    expect(labels.get(ticks[0])).toEqual({ time: '08:00', day: 'Fri' })
  })
})


describe('formatKg', () => {
  it.each([
    { name: '0 gives "0"', value: 0, expected: '0' },
    { name: '0.5 gives "0.500"', value: 0.5, expected: '0.500' },
    { name: '1.234 gives "1.234"', value: 1.234, expected: '1.234' },
  ])(': $name', ({ value, expected }) => {
    expect(formatKg(value)).toBe(expected)
  })
})