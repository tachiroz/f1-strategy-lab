import { describe, expect, it } from 'vitest'
import type { CircuitSummary, RaceDetail, RaceSummary } from '../api/types'
import circuitsFixture from '../test/fixtures/circuits.json'
import raceFixture from '../test/fixtures/race-202504.json'
import racesFixture from '../test/fixtures/races.json'
import { defaultDriverId, defaultRaceId, resolveCircuitId, resolveRaceId } from './selection'

const races = racesFixture as RaceSummary[]
const race = raceFixture as RaceDetail
const circuits = circuitsFixture as CircuitSummary[]

describe('race selection', () => {
  it('opens the showcase race by default', () => {
    expect(defaultRaceId(races)).toBe(202504)
  })

  it('falls back to the latest simulated race without the showcase', () => {
    const others = races.filter((item) => item.race_id !== 202504)
    const latest = others.filter((item) => item.simulatable).at(-1)
    expect(defaultRaceId(others)).toBe(latest?.race_id)
  })

  it('takes the race from the URL when it exists', () => {
    expect(resolveRaceId('202501', races)).toBe(202501)
    expect(resolveRaceId('190001', races)).toBe(202504)
    expect(resolveRaceId(null, races)).toBe(202504)
    expect(resolveRaceId('202501', undefined)).toBeUndefined()
  })
})

describe('defaultDriverId', () => {
  it('prefers the showcase driver, else the winner, else the first starter', () => {
    expect(defaultDriverId(race)).toBe('piastri')
    const others = race.drivers.filter((item) => item.driver_id !== 'piastri')
    const crowned = others.map((item) =>
      item.driver_id === 'norris' ? { ...item, finish_position: 1 } : item,
    )
    expect(defaultDriverId({ ...race, drivers: crowned })).toBe('norris')
    expect(defaultDriverId({ ...race, drivers: others })).toBe(others[0].driver_id)
  })
})

describe('resolveCircuitId', () => {
  it('uses the URL circuit, then the race circuit, then the showcase circuit', () => {
    expect(resolveCircuitId('monaco', undefined, circuits)).toBe('monaco')
    expect(resolveCircuitId(null, 'suzuka', circuits)).toBe('suzuka')
    expect(resolveCircuitId('nowhere', 'nowhere', circuits)).toBe('bahrain')
    expect(resolveCircuitId(null, undefined, [])).toBeUndefined()
  })
})
