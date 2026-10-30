import { describe, expect, it } from 'vitest'
import { formatUk } from './time'

describe('formatUk', () => {
  it("UTC time remains unchanged in winter (GMT)", () => {
    expect(formatUk('2026-10-30T15:00:00Z')).toBe('Fri 15:00')
  })
  it ("adds 1 hour to UTC time in summer (BST)", () => {
    expect(formatUk('2026-10-23T23:30:00Z')).toBe('Sat 00:30')
  })
})


