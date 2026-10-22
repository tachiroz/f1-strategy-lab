/**
 * Responses of the f1lab API, mirroring src/f1lab/api/schemas.py.
 * Positions are 1-based, probabilities are shares in [0, 1], intervals are 95% CIs.
 */

export interface Health {
  status: string
  version: string
}

export interface Interval {
  value: number
  low: number
  high: number
}

export interface RaceSummary {
  race_id: number
  season: number
  round: number
  race_name: string
  circuit_id: string
  circuit_name: string
  country: string | null
  date: string
  /** The season is part of the calibration: the simulator has seen this race. */
  in_sample: boolean
  simulatable: boolean
  reason: string | null
}

export interface Stint {
  compound: string
  first_lap: number
  last_lap: number
}

export interface StrategyOut {
  notation: string
  stints: Stint[]
  /** The driver retired before showing a strategy; the field's most common one is used. */
  stand_in: boolean
}

export interface DriverEntry {
  driver_id: string
  code: string | null
  name: string
  team: string
  /** Official grid position, 0 for a pit-lane start. */
  grid: number
  quali_position: number | null
  finish_position: number | null
  status: string
  strategy: StrategyOut | null
}

export interface FieldStrategy {
  notation: string
  drivers: number
}

export interface RaceDetail extends RaceSummary {
  race_laps: number
  drivers: DriverEntry[]
  field_strategies: FieldStrategy[]
}

export interface PositionStats {
  mean_position: Interval
  median_position: number
  /** 10-90% spread of the simulated position, retirements included (classified last). */
  band_low: number
  band_high: number
  finish_mean: number | null
  /** 10-90% spread of the position over the runs in which the car finishes. */
  finish_low: number | null
  finish_high: number | null
  p_win: Interval
  p_podium: Interval
  p_points: Interval
  p_retire: number
  /** Share of runs classified 1st ... last, then the share of retirements. */
  histogram: number[]
}

export interface DriverOutcome extends PositionStats {
  driver_id: string
  grid: number
  actual_position: number | null
}

export interface RaceScore {
  finishers: number
  spearman: number | null
  grid_spearman: number | null
  mae: number
  grid_mae: number
}

export interface RaceSimulation {
  race_id: number
  runs: number
  seed: number
  p_safety_car: number
  p_virtual_safety_car: number
  score: RaceScore | null
  drivers: DriverOutcome[]
}

export interface StrategyOutcome extends PositionStats {
  label: string
  notation: string
  stints: Stint[]
  is_actual: boolean
  /** Paired difference of the mean position to the actual strategy (negative = better). */
  delta: Interval
}

export interface StrategyComparison {
  race_id: number
  driver_id: string
  runs: number
  strategies: StrategyOutcome[]
}

export interface SensitivityPoint {
  scale: number
  p_safety_car: number
  mean_position: Interval
  p_podium: number
  p_points: number
}

export interface SensitivitySeries {
  label: string
  notation: string
  is_actual: boolean
  points: SensitivityPoint[]
}

export interface ScSensitivity {
  race_id: number
  driver_id: string
  runs: number
  /** Multipliers of the circuit's historical SC and VSC probabilities. */
  scales: number[]
  series: SensitivitySeries[]
}

export interface CircuitSummary {
  circuit_id: string
  circuit_name: string
  country: string | null
  laps: number
  compounds: string[]
  degradation_s_per_lap: Record<string, Interval>
}

export interface CurvePoint {
  age: number
  delta_s: number
  low: number
  high: number
}

export interface ObservedPoint {
  age: number
  delta_s: number
  laps: number
}

export interface TyreCompound {
  compound: string
  laps: number
  offset_s: Interval
  degradation_s_per_lap: Interval
  max_tyre_age: number
  curve: CurvePoint[]
  observed: ObservedPoint[]
}

export interface TyreModel {
  circuit_id: string
  circuit_name: string
  seasons: number[]
  reference_compound: string
  fuel_s_per_lap: Interval
  residual_sd_s: number
  laps: number
  compounds: TyreCompound[]
}
