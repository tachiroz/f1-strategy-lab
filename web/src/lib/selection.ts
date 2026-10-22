/** What a page shows when the URL does not say: race, driver and circuit defaults. */
import type { CircuitSummary, RaceDetail, RaceSummary } from '../api/types'
import { SHOWCASE } from '../config'

/** The race to open when the URL names none: the showcase race, else the latest simulated one. */
export function defaultRaceId(races: readonly RaceSummary[]): number | undefined {
  const showcase = races.find((race) => race.race_id === SHOWCASE.raceId && race.simulatable)
  return (showcase ?? races.findLast((race) => race.simulatable) ?? races.at(-1))?.race_id
}

/** Race from the URL if it exists, otherwise the default one. */
export function resolveRaceId(
  requested: string | null,
  races: readonly RaceSummary[] | undefined,
): number | undefined {
  if (!races) return undefined
  const id = Number(requested)
  return races.some((race) => race.race_id === id) ? id : defaultRaceId(races)
}

/** Driver to show when the URL names none: the showcase driver, else the winner. */
export function defaultDriverId(race: RaceDetail): string | undefined {
  const candidates = race.drivers.filter((driver) => driver.strategy)
  return (
    candidates.find((driver) => driver.driver_id === SHOWCASE.driverId) ??
    candidates.find((driver) => driver.finish_position === 1) ??
    candidates[0]
  )?.driver_id
}

/** Circuit from the URL, else that of the race in the URL, else the showcase or first one. */
export function resolveCircuitId(
  circuitParam: string | null,
  raceCircuit: string | undefined,
  circuits: readonly CircuitSummary[],
): string | undefined {
  const known = (id: string | null | undefined) => circuits.some((c) => c.circuit_id === id)
  if (known(circuitParam)) return circuitParam ?? undefined
  if (known(raceCircuit)) return raceCircuit
  return (
    circuits.find((circuit) => circuit.circuit_id === SHOWCASE.circuitId)?.circuit_id ??
    circuits[0]?.circuit_id
  )
}
