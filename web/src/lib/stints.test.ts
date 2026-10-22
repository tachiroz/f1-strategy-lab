import { describe, expect, it } from 'vitest'
import { describeStints, stintLabel, stintLaps } from './stints'

describe('stintLabel', () => {
  it('picks the longest label that fits without clipping', () => {
    expect(stintLabel('Medium', 18, 200)).toBe('Medium · 18')
    expect(stintLabel('Medium', 18, 60)).toBe('M · 18')
    expect(stintLabel('Medium', 18, 30)).toBe('M')
    expect(stintLabel('Medium', 18, 10)).toBe('')
  })
})

describe('stint helpers', () => {
  it('counts laps inclusively and describes stints for screen readers', () => {
    const stints = [
      { compound: 'SOFT', first_lap: 1, last_lap: 14 },
      { compound: 'MEDIUM', first_lap: 15, last_lap: 57 },
    ]
    expect(stintLaps(stints[0])).toBe(14)
    expect(describeStints(stints)).toBe('Soft, круги 1–14; Medium, круги 15–57')
  })
})
