import { describe, expect, it } from 'vitest'
import type { Slot } from './types'
import { describePlan, groupSlots } from './plan'


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
            intensity: {forecast: 0, actual: null, index: 'low',}, //placeholder
        })
    }
    return slots
}



describe('describePlan', () => {
  it("uses singular 'slot' for one slot", () => {
    expect(describePlan(makeSlots(1))).toBe('Charging during 1 half-hour slot (0.5 hours).')
  })
  it ("uses singular 'hour' for one hour", () => {
    expect(describePlan(makeSlots(2))).toBe('Charging during 2 half-hour slots (1 hour).')
  })
  it ("uses plural for both in all other cases", () => {
    expect(describePlan(makeSlots(3))).toBe('Charging during 3 half-hour slots (1.5 hours).')
  })
})

// const alphaNumeric = alpha.concat(numeric); 


describe('groupSlots', () => {
  it("returns one slots if they are adjacent", () => {
    expect(groupSlots(makeSlots(4)).length).toBe(1)
  })
  it("returns more than one slot if not adjacent", () => {
    expect(groupSlots([...makeSlots(4), ...(makeSlots(4, "31"))]).length).toBe(2)
  })
})

