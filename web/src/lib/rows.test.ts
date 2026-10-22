import { describe, expect, it } from 'vitest'
import type { CircuitSummary, RaceDetail, RaceSimulation } from '../api/types'
import circuitsFixture from '../test/fixtures/circuits.json'
import raceFixture from '../test/fixtures/race-202504.json'
import simulationFixture from '../test/fixtures/simulation-202504.json'
import { outcomeRows, slopeRows } from './rows'

const race = raceFixture as RaceDetail
const simulation = simulationFixture as RaceSimulation

describe('outcomeRows', () => {
  it('lists every simulated starter in the official finishing order', () => {
    const rows = outcomeRows(race, simulation)
    expect(rows).toHaveLength(simulation.drivers.length)
    expect(rows[0]).toMatchObject({ id: 'piastri', code: 'PIA', actual: 1, grid: 1 })
    const classified = rows.filter((row) => row.actual !== null).map((row) => row.actual)
    expect(classified).toEqual([...classified].sort((a, b) => (a ?? 0) - (b ?? 0)))
    expect(rows.at(-1)?.actual).toBeNull()
  })

  it('uses the band of the runs in which the car finishes', () => {
    const piastri = simulation.drivers.find((driver) => driver.driver_id === 'piastri')
    const row = outcomeRows(race, simulation)[0]
    expect([row.low, row.mean, row.high]).toEqual([
      piastri?.finish_low,
      piastri?.finish_mean,
      piastri?.finish_high,
    ])
  })
})

describe('slopeRows', () => {
  it('orders circuits by mean degradation, highest first', () => {
    const rows = slopeRows(circuitsFixture as CircuitSummary[])
    const mean = (values: Record<string, { value: number }>) => {
      const list = Object.values(values).map((item) => item.value)
      return list.reduce((a, b) => a + b, 0) / list.length
    }
    const means = rows.map((row) => mean(row.values))
    expect(means).toEqual([...means].sort((a, b) => b - a))
    expect(rows).toHaveLength(circuitsFixture.length)
  })
})
