/** Turn API responses into chart rows. */
import type { CircuitSummary, RaceDetail, RaceSimulation } from '../api/types'
import type { OutcomeRow } from '../charts/OutcomeChart'
import type { SlopeRow } from '../charts/SlopeDotPlot'

/** Rows of the outcome chart: classified finishers in finishing order, then the rest. */
export function outcomeRows(race: RaceDetail, simulation: RaceSimulation): OutcomeRow[] {
  const outcomes = new Map(simulation.drivers.map((driver) => [driver.driver_id, driver]))
  return race.drivers.flatMap((driver) => {
    const outcome = outcomes.get(driver.driver_id)
    if (!outcome) return []
    return [
      {
        id: driver.driver_id,
        code: driver.code ?? driver.driver_id.slice(0, 3).toUpperCase(),
        name: driver.name,
        grid: driver.grid,
        mean: outcome.finish_mean,
        low: outcome.finish_low,
        high: outcome.finish_high,
        actual: driver.finish_position,
        pRetire: outcome.p_retire,
      },
    ]
  })
}

/** Circuits ordered by their mean degradation over the compounds they have, highest first. */
export function slopeRows(circuits: readonly CircuitSummary[]): SlopeRow[] {
  const mean = (circuit: CircuitSummary) => {
    const values = Object.values(circuit.degradation_s_per_lap).map((slope) => slope.value)
    return values.reduce((total, value) => total + value, 0) / Math.max(values.length, 1)
  }
  return [...circuits]
    .sort((a, b) => mean(b) - mean(a))
    .map((circuit) => ({
      id: circuit.circuit_id,
      label: circuit.circuit_name,
      values: circuit.degradation_s_per_lap,
    }))
}
