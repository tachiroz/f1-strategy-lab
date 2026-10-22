import { Plus, X } from 'lucide-react'
import { type FormEvent, useId, useState } from 'react'
import { useSearchParams } from 'react-router'
import { useRace, useRaces, useScSensitivity, useStrategyComparison } from '../api/queries'
import type {
  DriverEntry,
  RaceDetail,
  ScSensitivity,
  StrategyComparison,
  StrategyOutcome,
} from '../api/types'
import { ChartCard } from '../charts/ChartCard'
import { type Column, DataTable } from '../charts/DataTable'
import { Legend, type LegendItem } from '../charts/Legend'
import { MarkerIcon } from '../charts/Marker'
import { PositionHistogram } from '../charts/PositionHistogram'
import { SensitivityChart } from '../charts/SensitivityChart'
import { STRATEGY_LETTERS, strategySeries } from '../charts/series'
import { Badge, Page, PageHeader } from '../components/PageHeader'
import { RacePicker } from '../components/RacePicker'
import { Select } from '../components/Select'
import { type Verdict } from '../components/StatTile'
import { ErrorState, Loading, Notice } from '../components/States'
import { StintBar } from '../components/StintBar'
import {
  formatInterval,
  formatNumber,
  formatPercent,
  formatScale,
  formatSigned,
} from '../lib/format'
import { defaultDriverId, resolveRaceId } from '../lib/selection'
import { parseStrategy } from '../lib/strategy'

/** The actual strategy plus up to two alternatives, as the API allows. */
export const MAX_ALTERNATIVES = 2
const FIELD_SUGGESTIONS = 6
const STRATEGY_PARAM = 's'

const LABELS = ['Фактическая', 'Вариант A', 'Вариант B'] as const

function deltaVerdict(outcome: StrategyOutcome): Verdict {
  if (outcome.delta.high < 0) return 'better'
  if (outcome.delta.low > 0) return 'worse'
  return 'same'
}

const VERDICT_TEXT: Record<Verdict, string> = {
  better: 'лучше фактической',
  worse: 'хуже фактической',
  same: 'разница в пределах шума',
}

const VERDICT_CLASS: Record<Verdict, string> = {
  better: 'text-success',
  worse: 'text-accent',
  same: 'text-ink-subtle',
}

function SeriesKey({ index }: { index: number }) {
  const style = strategySeries(index)
  return (
    <span
      aria-hidden="true"
      className="relative inline-flex w-5 shrink-0 items-center justify-center"
    >
      <span className={`h-0.5 w-5 rounded-full ${style.swatch}`} />
      <span className="absolute">
        <MarkerIcon shape={style.marker} className={style.fill} />
      </span>
    </span>
  )
}

interface EditorProps {
  race: RaceDetail
  driver: DriverEntry
  alternatives: readonly string[]
  onChange: (alternatives: string[]) => void
}

function StrategyEditor({ race, driver, alternatives, onChange }: EditorProps) {
  const [text, setText] = useState('')
  const inputId = useId()
  const messageId = useId()
  const actual = driver.strategy
  const parsed = text.trim() ? parseStrategy(text, race.race_laps) : null
  const taken = new Set([actual?.notation, ...alternatives])
  const duplicate = parsed?.ok && taken.has(parsed.notation)
  const full = alternatives.length >= MAX_ALTERNATIVES
  const suggestions = race.field_strategies
    .map((item) => item.notation)
    .filter((notation) => !taken.has(notation))
    .slice(0, FIELD_SUGGESTIONS)

  function add(notation: string) {
    if (full || taken.has(notation)) return
    onChange([...alternatives, notation])
    setText('')
  }

  function submit(event: FormEvent) {
    event.preventDefault()
    if (parsed?.ok && !duplicate) add(parsed.notation)
  }

  const rows = [
    ...(actual ? [{ notation: actual.notation, stints: actual.stints }] : []),
    ...alternatives.flatMap((notation) => {
      const result = parseStrategy(notation, race.race_laps)
      return result.ok ? [{ notation: result.notation, stints: result.stints }] : []
    }),
  ]

  return (
    <section
      aria-labelledby="editor-title"
      className="rounded-2xl border border-line bg-surface p-4 sm:p-6"
    >
      <h2 id="editor-title" className="font-semibold tracking-tight">
        Стратегии для сравнения
      </h2>
      <p className="mt-1 text-sm text-ink-muted">
        Остальные пилоты едут со своими реальными стратегиями. Все варианты считаются на одних и тех
        же случайных числах: те же Safety Car, сходы и шум.
      </p>

      <ul className="mt-5 space-y-3">
        {rows.map((row, index) => (
          <li
            key={row.notation}
            className="flex flex-wrap items-center gap-x-3 gap-y-2 sm:flex-nowrap"
          >
            <span className="order-1 flex shrink-0 items-center gap-2 text-sm sm:w-36">
              <SeriesKey index={index} />
              <span className={index === 0 ? 'font-medium' : ''}>{LABELS[index]}</span>
            </span>
            <StintBar
              stints={row.stints}
              raceLaps={race.race_laps}
              className="order-4 min-w-0 basis-full sm:order-2 sm:flex-1 sm:basis-0"
            />
            <code className="order-2 ml-auto shrink-0 font-mono text-xs text-ink-muted sm:order-3 sm:ml-0 sm:w-32">
              {row.notation}
            </code>
            {index > 0 ? (
              <button
                type="button"
                onClick={() => onChange(alternatives.filter((item) => item !== row.notation))}
                aria-label={`Убрать стратегию ${row.notation}`}
                className="order-3 inline-flex size-7 shrink-0 items-center justify-center rounded-md text-ink-subtle transition-colors hover:bg-white/5 hover:text-ink sm:order-4"
              >
                <X aria-hidden="true" className="size-4" />
              </button>
            ) : (
              <span className="order-3 size-7 shrink-0 sm:order-4" />
            )}
          </li>
        ))}
      </ul>
      {actual?.stand_in && (
        <p className="mt-2 text-xs text-ink-subtle">
          Пилот сошёл раньше, чем показал стратегию: за «фактическую» взята самая частая стратегия
          финишёров.
        </p>
      )}

      {!full && (
        <form onSubmit={submit} className="mt-6 border-t border-line pt-5">
          <label htmlFor={inputId} className="text-sm font-medium">
            Добавить стратегию
          </label>
          <div className="mt-2 flex flex-wrap gap-2">
            <input
              id={inputId}
              value={text}
              onChange={(event) => setText(event.target.value)}
              placeholder="например, M-25-H"
              autoComplete="off"
              spellCheck={false}
              aria-invalid={parsed !== null && (!parsed.ok || Boolean(duplicate))}
              aria-describedby={messageId}
              className="w-full min-w-0 flex-1 rounded-lg border border-line-strong bg-canvas px-3 py-2 font-mono text-sm text-ink uppercase placeholder:text-ink-subtle placeholder:normal-case focus-visible:border-accent focus-visible:outline-none aria-invalid:border-accent/70 sm:w-auto"
            />
            <button
              type="submit"
              disabled={!parsed?.ok || Boolean(duplicate)}
              className="inline-flex items-center gap-1.5 rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-40"
            >
              <Plus aria-hidden="true" className="size-4" />
              Добавить
            </button>
          </div>
          <div id={messageId} aria-live="polite" className="mt-2 min-h-5 text-xs">
            {parsed && !parsed.ok && <span className="text-accent">{parsed.error}</span>}
            {duplicate && <span className="text-accent">Такая стратегия уже есть в сравнении</span>}
            {parsed?.ok && !duplicate && (
              <StintBar
                stints={parsed.stints}
                raceLaps={race.race_laps}
                size="sm"
                className="max-w-md"
              />
            )}
            {!parsed && (
              <span className="text-ink-subtle">
                S, M, H — составы; число — круг пит-стопа; S3 — софты с 3 кругами пробега.{' '}
                {race.race_laps} кругов в гонке.
              </span>
            )}
          </div>
          {suggestions.length > 0 && (
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <span className="text-xs text-ink-subtle">Стратегии поля:</span>
              {suggestions.map((notation) => (
                <button
                  key={notation}
                  type="button"
                  onClick={() => add(notation)}
                  className="rounded-md border border-line-strong px-2 py-1 font-mono text-xs text-ink-muted transition-colors hover:border-ink-subtle hover:text-ink"
                >
                  {notation}
                </button>
              ))}
            </div>
          )}
        </form>
      )}
    </section>
  )
}

function StrategyCards({ comparison }: { comparison: StrategyComparison }) {
  const raceLaps = comparison.strategies[0]?.stints.at(-1)?.last_lap ?? 1
  return (
    <ul className="grid gap-3 md:grid-cols-3">
      {comparison.strategies.map((outcome, index) => {
        const verdict = deltaVerdict(outcome)
        return (
          <li key={outcome.notation} className="rounded-2xl border border-line bg-surface p-5">
            <div className="flex items-center justify-between gap-2">
              <span className="flex items-center gap-2 text-sm font-medium">
                <SeriesKey index={index} />
                {LABELS[index]}
              </span>
              <code className="font-mono text-xs text-ink-subtle">{outcome.notation}</code>
            </div>
            <StintBar stints={outcome.stints} raceLaps={raceLaps} size="sm" className="mt-3" />
            <dl className="mt-4">
              <dt className="text-xs text-ink-subtle">Средняя позиция</dt>
              <dd className="mt-1 flex items-baseline gap-2">
                <span className="text-3xl font-semibold tracking-tight">
                  {formatNumber(outcome.mean_position.value)}
                </span>
                <span className="font-mono text-xs text-ink-subtle tabular-nums">
                  {formatInterval(outcome.mean_position.low, outcome.mean_position.high)}
                </span>
              </dd>
            </dl>
            <dl className="mt-4 grid grid-cols-4 gap-2 text-center">
              {(
                [
                  ['Победа', outcome.p_win.value],
                  ['Подиум', outcome.p_podium.value],
                  ['Очки', outcome.p_points.value],
                  ['Сход', outcome.p_retire],
                ] as const
              ).map(([label, value]) => (
                <div key={label} className="rounded-lg bg-canvas/60 px-1 py-2">
                  <dt className="text-[11px] text-ink-subtle">{label}</dt>
                  <dd className="mt-0.5 font-mono text-sm tabular-nums">{formatPercent(value)}</dd>
                </div>
              ))}
            </dl>
            <p
              className={`mt-4 text-xs ${outcome.is_actual ? 'text-ink-subtle' : VERDICT_CLASS[verdict]}`}
            >
              {outcome.is_actual ? (
                'Точка отсчёта для разницы'
              ) : (
                <>
                  <span className="font-mono tabular-nums">
                    {formatSigned(outcome.delta.value)}{' '}
                    {formatInterval(outcome.delta.low, outcome.delta.high, 2, true)}
                  </span>{' '}
                  позиции: {VERDICT_TEXT[verdict]}
                </>
              )}
            </p>
          </li>
        )
      })}
    </ul>
  )
}

function strategyLegend(notations: readonly string[]): LegendItem[] {
  return notations.map((notation, index) => ({
    label: `${LABELS[index]} · ${notation}`,
    key: {
      kind: 'line',
      swatch: strategySeries(index).swatch,
      marker: { shape: strategySeries(index).marker, fill: strategySeries(index).fill },
    },
  }))
}

function histogramColumns(comparison: StrategyComparison): Column<number>[] {
  const fieldSize = (comparison.strategies[0]?.histogram.length ?? 1) - 1
  return [
    {
      key: 'position',
      header: 'Позиция',
      cell: (index) => (index === fieldSize ? 'Сход' : `P${index + 1}`),
    },
    ...comparison.strategies.map((outcome, index) => ({
      key: outcome.notation,
      header: `${STRATEGY_LETTERS[index]} · ${outcome.notation}`,
      numeric: true,
      cell: (row: number) => formatPercent(outcome.histogram[row]),
    })),
  ]
}

interface SensitivityRow {
  scale: number
  index: number
}

function sensitivityColumns(sensitivity: ScSensitivity): Column<SensitivityRow>[] {
  return [
    { key: 'scale', header: 'Частота SC', cell: (row) => formatScale(row.scale) },
    {
      key: 'share',
      header: 'Гонок с SC',
      numeric: true,
      cell: (row) => formatPercent(sensitivity.series[0]?.points[row.index]?.p_safety_car ?? 0),
    },
    ...sensitivity.series.map((series, index) => ({
      key: series.notation,
      header: `${STRATEGY_LETTERS[index]} · ${series.notation}`,
      numeric: true,
      cell: (row: SensitivityRow) => {
        const point = series.points[row.index]
        return `${formatNumber(point.mean_position.value)} ${formatInterval(point.mean_position.low, point.mean_position.high, 1)}`
      },
    })),
  ]
}

interface ResultsProps {
  comparison: StrategyComparison
  sensitivity: ScSensitivity | undefined
  comparing: boolean
  sensing: boolean
  sensitivityError: unknown
}

function Results({ comparison, sensitivity, comparing, sensing, sensitivityError }: ResultsProps) {
  const fieldSize = (comparison.strategies[0]?.histogram.length ?? 1) - 1
  return (
    <>
      <div
        className={`transition-opacity duration-300 ${comparing ? 'opacity-50' : ''}`}
        aria-busy={comparing}
      >
        <StrategyCards comparison={comparison} />
      </div>

      <ChartCard
        title="Распределение финишной позиции"
        description="Доля прогонов, в которых пилот финиширует на каждой позиции; справа — доля сходов."
        busy={comparing}
        legend={<Legend items={strategyLegend(comparison.strategies.map((s) => s.notation))} />}
        table={
          <DataTable
            caption="Распределение финишной позиции по стратегиям"
            columns={histogramColumns(comparison)}
            rows={Array.from({ length: fieldSize + 1 }, (_, index) => index)}
            rowKey={(row) => String(row)}
          />
        }
        footnote={`${formatNumber(comparison.runs, 0)} прогонов на стратегию.`}
      >
        <PositionHistogram
          fieldSize={fieldSize}
          series={comparison.strategies.map((outcome, index) => ({
            id: outcome.notation,
            label: `${LABELS[index]} · ${outcome.notation}`,
            values: outcome.histogram,
            style: strategySeries(index),
          }))}
        />
      </ChartCard>

      {sensitivityError ? (
        <ErrorState error={sensitivityError} />
      ) : sensitivity ? (
        <ChartCard
          title="Чувствительность к Safety Car"
          description="Средняя позиция, если SC и VSC выезжают реже или чаще, чем обычно на этой трассе. Выше — лучше."
          busy={sensing}
          legend={<Legend items={strategyLegend(sensitivity.series.map((s) => s.notation))} />}
          table={
            <DataTable
              caption="Средняя позиция при разной частоте Safety Car"
              columns={sensitivityColumns(sensitivity)}
              rows={sensitivity.scales.map((scale, index) => ({ scale, index }))}
              rowKey={(row) => String(row.scale)}
            />
          }
          footnote={`${formatNumber(sensitivity.runs, 0)} прогонов на точку, поэтому значения при ×1 могут немного отличаться от карточек выше (${formatNumber(comparison.runs, 0)} прогонов). Под осью — доля гонок хотя бы с одним SC.`}
        >
          <SensitivityChart
            scales={sensitivity.scales}
            lines={sensitivity.series.map((series, index) => ({
              id: series.notation,
              tag: STRATEGY_LETTERS[index],
              label: `${LABELS[index]} · ${series.notation}`,
              points: series.points,
              style: strategySeries(index),
            }))}
          />
        </ChartCard>
      ) : (
        <Loading label="Считаем чувствительность к Safety Car…" />
      )}
    </>
  )
}

export function StrategyPage() {
  const [params, setParams] = useSearchParams()
  const races = useRaces()
  const simulated = races.data?.filter((race) => race.simulatable)
  const raceId = resolveRaceId(params.get('race'), simulated)
  const race = useRace(raceId)
  const drivers = race.data?.drivers.filter((driver) => driver.strategy) ?? []
  const requested = drivers.find((driver) => driver.driver_id === params.get('driver'))
  const driver =
    requested ??
    drivers.find((item) => item.driver_id === (race.data && defaultDriverId(race.data)))
  const alternatives = params.getAll(STRATEGY_PARAM).slice(0, MAX_ALTERNATIVES)
  const request = {
    raceId: race.data?.race_id,
    driverId: driver?.driver_id,
    strategies: alternatives,
  }
  const comparison = useStrategyComparison(request)
  const sensitivity = useScSensitivity(request)

  function update(next: { race?: number; driver?: string; strategies?: string[] }) {
    const search = new URLSearchParams()
    search.set('race', String(next.race ?? raceId))
    const nextDriver = next.race === undefined ? (next.driver ?? driver?.driver_id) : undefined
    if (nextDriver) search.set('driver', nextDriver)
    for (const notation of next.race === undefined ? (next.strategies ?? alternatives) : []) {
      search.append(STRATEGY_PARAM, notation)
    }
    setParams(search)
  }

  if (races.isError)
    return (
      <Page>
        <title>Стратегии · F1 Strategy Lab</title>
        <ErrorState error={races.error} />
      </Page>
    )
  if (!races.data)
    return (
      <Page>
        <title>Стратегии · F1 Strategy Lab</title>
        <Loading label="Калибруем симулятор и загружаем гонки…" />
      </Page>
    )
  if (raceId === undefined) {
    return (
      <Page>
        <title>Стратегии · F1 Strategy Lab</title>
        <Notice title="Нет гонок, которые можно симулировать">
          Загрузите данные: <code className="font-mono">python -m f1lab.ingest</code>.
        </Notice>
      </Page>
    )
  }

  const current = comparison.data
  const matches =
    current !== undefined && current.race_id === raceId && current.driver_id === driver?.driver_id

  return (
    <Page>
      <title>Стратегии · F1 Strategy Lab</title>
      <PageHeader
        eyebrow="Стратегии"
        title={driver ? `${driver.name}: какая стратегия лучше` : 'Сравнение стратегий'}
        description="Фактическая стратегия пилота против одной-двух альтернатив. Средняя позиция с 95% интервалом, вероятности подиума и очков, распределение финиша и чувствительность к Safety Car."
        aside={
          race.data && (
            <Badge>
              {race.data.race_name} {race.data.season}
            </Badge>
          )
        }
      />

      <div className="flex flex-wrap items-end gap-3">
        <RacePicker
          races={races.data}
          value={raceId}
          simulatableOnly
          onChange={(next) => update({ race: next })}
        />
        {race.data && driver && (
          <Select
            label="Пилот"
            value={driver.driver_id}
            onChange={(next) => update({ driver: next })}
            className="w-full sm:w-72"
            options={drivers.map((item) => ({
              value: item.driver_id,
              label: `${item.finish_position ? `P${item.finish_position}` : 'сход'} · ${item.code ?? ''} · ${item.name}`,
            }))}
          />
        )}
      </div>

      {race.isError && <ErrorState error={race.error} />}
      {race.data && driver && (
        <StrategyEditor
          race={race.data}
          driver={driver}
          alternatives={alternatives}
          onChange={(strategies) => update({ strategies })}
        />
      )}

      {comparison.isError && <ErrorState error={comparison.error} />}
      {!comparison.isError && !matches && <Loading label="Считаем стратегии…" />}
      {matches && (
        <Results
          comparison={current}
          sensitivity={
            sensitivity.data?.driver_id === driver?.driver_id ? sensitivity.data : undefined
          }
          comparing={comparison.isPlaceholderData || comparison.isFetching}
          sensing={sensitivity.isPlaceholderData || sensitivity.isFetching}
          sensitivityError={sensitivity.isError ? sensitivity.error : undefined}
        />
      )}
    </Page>
  )
}
