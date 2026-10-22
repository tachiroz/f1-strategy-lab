import { ArrowRight } from 'lucide-react'
import { Link } from 'react-router'
import { ApiError } from '../api/client'
import { useRace, useSimulation } from '../api/queries'
import type { Stint } from '../api/types'
import { SHOWCASE } from '../config'
import { COMPOUNDS } from '../data/compounds'
import { formatNumber, formatPercent, pluralize } from '../lib/format'
import { StintBar } from './StintBar'

/** Shown while the API is not available: an illustration, never presented as data. */
const EXAMPLE_STINTS: readonly Stint[] = [
  { compound: 'MEDIUM', first_lap: 1, last_lap: 18 },
  { compound: 'HARD', first_lap: 19, last_lap: 43 },
  { compound: 'SOFT', first_lap: 44, last_lap: 58 },
]

const METRICS = ['Средняя позиция', 'P(подиум)', 'P(очки)'] as const

/** Hero card: the showcase driver's real strategy and simulated outcome, live from the API. */
export function StrategyPreview() {
  const race = useRace(SHOWCASE.raceId)
  const simulation = useSimulation(SHOWCASE.raceId)
  const driver = race.data?.drivers.find((item) => item.driver_id === SHOWCASE.driverId)
  const outcome = simulation.data?.drivers.find((item) => item.driver_id === SHOWCASE.driverId)
  const live = Boolean(race.data && driver?.strategy)
  const stints = driver?.strategy?.stints ?? EXAMPLE_STINTS
  const raceLaps = race.data?.race_laps ?? EXAMPLE_STINTS[EXAMPLE_STINTS.length - 1].last_lap
  const pitLaps = stints.slice(0, -1).map((stint) => stint.last_lap)
  const error = race.error ?? simulation.error
  const values = outcome
    ? [
        formatNumber(outcome.mean_position.value, 1),
        formatPercent(outcome.p_podium.value),
        formatPercent(outcome.p_points.value),
      ]
    : METRICS.map(() => '—')

  return (
    <div className="relative rounded-2xl border border-line bg-surface/70 p-5 shadow-2xl shadow-black/40 backdrop-blur sm:p-6">
      <div
        aria-hidden="true"
        className="absolute inset-x-10 -top-px h-px bg-linear-to-r from-transparent via-accent/80 to-transparent"
      />

      <div className="flex items-center justify-between gap-4">
        <h2 className="text-sm font-medium">
          {live && race.data ? `${race.data.race_name} ${race.data.season}` : 'Анатомия стратегии'}
        </h2>
        <span className="rounded-full border border-line px-2.5 py-0.5 font-mono text-[11px] text-ink-subtle">
          {live ? 'расчёт симулятора' : 'иллюстрация'}
        </span>
      </div>
      <p className="mt-1 text-sm text-ink-muted">
        {live && driver
          ? `${driver.name}, реальная стратегия ${driver.strategy?.notation}: `
          : 'Стратегия: список пит-стопов (круг, состав шин). '}
        {pitLaps.length} {pluralize(pitLaps.length, ['остановка', 'остановки', 'остановок'])},{' '}
        {raceLaps} {pluralize(raceLaps, ['круг', 'круга', 'кругов'])}.
      </p>

      <StintBar stints={stints} raceLaps={raceLaps} size="lg" className="mt-6" />

      <div className="relative mt-2 h-4 font-mono text-[10px] text-ink-subtle tabular-nums">
        <span className="absolute left-0">L1</span>
        {pitLaps.map((lap) => (
          <span
            key={lap}
            style={{ left: `${(lap / raceLaps) * 100}%` }}
            className="absolute -translate-x-1/2 text-ink-muted"
          >
            PIT L{lap}
          </span>
        ))}
        <span className="absolute right-0">L{raceLaps}</span>
      </div>

      <ul className="mt-5 flex flex-wrap gap-x-4 gap-y-2" aria-label="Цвета составов шин">
        {COMPOUNDS.map((compound) => (
          <li key={compound.id} className="flex items-center gap-1.5 text-xs text-ink-muted">
            <span aria-hidden="true" className={`${compound.swatch} size-2.5 rounded-full`} />
            {compound.label}
          </li>
        ))}
      </ul>

      <dl className="mt-6 grid grid-cols-3 gap-2 sm:gap-3">
        {METRICS.map((metric, index) => (
          <div key={metric} className="rounded-xl border border-line bg-canvas/60 p-3">
            <dt className="text-[11px] leading-tight text-ink-subtle sm:text-xs">{metric}</dt>
            <dd
              className={`mt-2 text-2xl font-semibold ${outcome ? 'text-ink' : 'text-ink-muted'}`}
            >
              {values[index]}
            </dd>
          </div>
        ))}
      </dl>
      <p className="mt-3 text-xs text-ink-subtle">
        {error instanceof ApiError && error.unreachable ? (
          <>
            Запустите API (<code className="font-mono">uvicorn f1lab.api.main:app</code>), чтобы
            увидеть расчёт.
          </>
        ) : outcome && simulation.data ? (
          <Link
            to={`/strategy?race=${SHOWCASE.raceId}&driver=${SHOWCASE.driverId}`}
            className="inline-flex items-center gap-1 text-ink-muted transition-colors hover:text-ink"
          >
            {formatNumber(simulation.data.runs, 0)} прогонов Монте-Карло · сравнить стратегии
            <ArrowRight aria-hidden="true" className="size-3.5" />
          </Link>
        ) : error ? (
          'Не получилось получить расчёт от API.'
        ) : (
          'Считаем симуляцию гонки…'
        )}
      </p>
    </div>
  )
}
