import { ArrowRight } from 'lucide-react'
import { Link, useSearchParams } from 'react-router'
import { useRace, useRaces, useSimulation } from '../api/queries'
import type { DriverEntry, DriverOutcome, RaceDetail, RaceSimulation } from '../api/types'
import { ChartCard } from '../charts/ChartCard'
import { type Column, DataTable } from '../charts/DataTable'
import { Legend } from '../charts/Legend'
import { OutcomeChart, type OutcomeRow } from '../charts/OutcomeChart'
import { Badge, Page, PageHeader } from '../components/PageHeader'
import { RacePicker } from '../components/RacePicker'
import { StatTile, type Verdict } from '../components/StatTile'
import { ErrorState, Loading, Notice } from '../components/States'
import { StintBar } from '../components/StintBar'
import { POINTS_POSITIONS } from '../config'
import {
  formatDate,
  formatInterval,
  formatNumber,
  formatPercent,
  formatSigned,
  pluralize,
} from '../lib/format'
import { outcomeRows } from '../lib/rows'
import { resolveRaceId } from '../lib/selection'
import { describeSetupReason } from '../lib/strategy'

function verdict(model: number, baseline: number, lowerIsBetter: boolean): Verdict {
  if (model === baseline) return 'same'
  return model < baseline === lowerIsBetter ? 'better' : 'worse'
}

function gridText(grid: number): string {
  return grid === 0 ? 'ПЛ' : String(grid)
}

function RaceKpis({ simulation }: { simulation: RaceSimulation }) {
  const score = simulation.score
  return (
    <dl className="grid grid-cols-2 gap-3 lg:grid-cols-4">
      {score && (
        <StatTile
          label="Ошибка прогноза"
          value={formatNumber(score.mae)}
          unit="поз."
          hint={`средняя по ${score.finishers} финишёрам; решётка ${formatNumber(score.grid_mae)}`}
          verdict={{
            kind: verdict(score.mae, score.grid_mae, true),
            text: `${formatSigned(score.mae - score.grid_mae)} к модели «финиш = решётка»`,
          }}
        />
      )}
      {score?.spearman != null && score.grid_spearman != null && (
        <StatTile
          label="Совпадение порядка (Spearman)"
          value={formatNumber(score.spearman)}
          hint={`у решётки ${formatNumber(score.grid_spearman)}; 1 — порядок угадан полностью`}
          verdict={{
            kind: verdict(score.spearman, score.grid_spearman, false),
            text: `${formatSigned(score.spearman - score.grid_spearman)} к решётке`,
          }}
        />
      )}
      <StatTile
        label="Safety Car в гонке"
        value={formatPercent(simulation.p_safety_car)}
        hint={`доля прогонов хотя бы с одним SC; VSC — ${formatPercent(simulation.p_virtual_safety_car)}`}
      />
      <StatTile
        label="Прогонов Монте-Карло"
        value={formatNumber(simulation.runs, 0)}
        hint={`seed ${simulation.seed}: тот же запрос — тот же ответ`}
      />
    </dl>
  )
}

const OUTCOME_COLUMNS: readonly Column<OutcomeRow>[] = [
  { key: 'driver', header: 'Пилот', cell: (row) => `${row.code} · ${row.name}` },
  { key: 'grid', header: 'Старт', numeric: true, cell: (row) => gridText(row.grid) },
  {
    key: 'mean',
    header: 'Симуляция, среднее',
    numeric: true,
    cell: (row) => (row.mean === null ? '—' : formatNumber(row.mean, 1)),
  },
  {
    key: 'band',
    header: '80% прогонов',
    numeric: true,
    cell: (row) =>
      row.low === null || row.high === null
        ? '—'
        : `${Math.round(row.low)}–${Math.round(row.high)}`,
  },
  {
    key: 'actual',
    header: 'Факт',
    numeric: true,
    cell: (row) => (row.actual === null ? 'сход' : row.actual),
  },
]

interface FieldRow {
  driver: DriverEntry
  outcome: DriverOutcome
}

function fieldColumns(race: RaceDetail): Column<FieldRow>[] {
  return [
    {
      key: 'driver',
      header: 'Пилот',
      cell: ({ driver }) => (
        <span className="flex flex-col">
          <span className="font-medium text-ink">
            <span className="font-mono text-ink-muted">{driver.code}</span> {driver.name}
          </span>
          <span className="text-xs text-ink-subtle">{driver.team}</span>
        </span>
      ),
    },
    { key: 'grid', header: 'Старт', numeric: true, cell: ({ driver }) => gridText(driver.grid) },
    {
      key: 'strategy',
      header: 'Стратегия',
      className: 'w-44',
      cell: ({ driver }) =>
        driver.strategy && (
          <span className="flex flex-col gap-1">
            <StintBar stints={driver.strategy.stints} raceLaps={race.race_laps} size="sm" />
            <span className="font-mono text-xs text-ink-subtle">
              {driver.strategy.notation}
              {driver.strategy.stand_in && ' *'}
            </span>
          </span>
        ),
    },
    {
      key: 'mean',
      header: 'Средняя позиция',
      numeric: true,
      cell: ({ outcome }) => (
        <span className="flex flex-col">
          <span className="text-ink">{formatNumber(outcome.mean_position.value)}</span>
          <span className="text-xs text-ink-subtle">
            {formatInterval(outcome.mean_position.low, outcome.mean_position.high, 1)}
          </span>
        </span>
      ),
    },
    {
      key: 'win',
      header: 'Победа',
      numeric: true,
      cell: ({ outcome }) => formatPercent(outcome.p_win.value),
    },
    {
      key: 'podium',
      header: 'Подиум',
      numeric: true,
      cell: ({ outcome }) => formatPercent(outcome.p_podium.value),
    },
    {
      key: 'points',
      header: 'Очки',
      numeric: true,
      cell: ({ outcome }) => formatPercent(outcome.p_points.value),
    },
    {
      key: 'retire',
      header: 'Сход',
      numeric: true,
      cell: ({ outcome }) => formatPercent(outcome.p_retire),
    },
    {
      key: 'actual',
      header: 'Факт',
      numeric: true,
      cell: ({ driver }) => driver.finish_position ?? 'сход',
    },
    {
      key: 'link',
      header: <span className="sr-only">Стратегии пилота</span>,
      cell: ({ driver }) => (
        <Link
          to={`/strategy?race=${race.race_id}&driver=${driver.driver_id}`}
          aria-label={`Сравнить стратегии: ${driver.name}`}
          className="inline-flex size-7 items-center justify-center rounded-md text-ink-subtle transition-colors hover:bg-white/5 hover:text-ink"
        >
          <ArrowRight aria-hidden="true" className="size-4" />
        </Link>
      ),
    },
  ]
}

function SimulatedRace({ race, simulation }: { race: RaceDetail; simulation: RaceSimulation }) {
  const rows = outcomeRows(race, simulation)
  const drivers = new Map(race.drivers.map((driver) => [driver.driver_id, driver]))
  const field: FieldRow[] = simulation.drivers.flatMap((outcome) => {
    const driver = drivers.get(outcome.driver_id)
    return driver ? [{ driver, outcome }] : []
  })
  return (
    <>
      <RaceKpis simulation={simulation} />

      <ChartCard
        title="Прогноз против факта"
        description="Симулятор знает квалификацию, решётку и стратегии, которые пилоты реально выбрали. Полоса — где пилот финиширует в 80% прогонов без схода, точка — среднее; ромб — реальный финиш, кольцо — старт (модель «финиш = решётка»)."
        legend={
          <Legend
            items={[
              { label: 'симуляция: 80% прогонов', key: { kind: 'band', swatch: 'bg-series-1' } },
              {
                label: 'среднее в симуляции',
                key: { kind: 'marker', shape: 'circle', fill: 'fill-series-1' },
              },
              {
                label: 'реальный финиш',
                key: { kind: 'marker', shape: 'diamond', fill: 'fill-ink' },
              },
              { label: 'старт', key: { kind: 'ring' } },
            ]}
          />
        }
        table={
          <DataTable
            caption="Симулированные и реальные позиции"
            columns={OUTCOME_COLUMNS}
            rows={rows}
            rowKey={(row) => row.id}
            muted={(row) => row.actual === null}
          />
        }
        footnote={`Светлая область — зона очков (P1–P${POINTS_POSITIONS}). Сошедшие в реальности пилоты внизу; в оценку точности они не входят.`}
      >
        <OutcomeChart
          rows={rows}
          fieldSize={race.drivers.length}
          pointsPositions={POINTS_POSITIONS}
        />
      </ChartCard>

      <section
        aria-labelledby="field-title"
        className="rounded-2xl border border-line bg-surface p-4 sm:p-6"
      >
        <h2 id="field-title" className="font-semibold tracking-tight">
          Все пилоты
        </h2>
        <p className="mt-1 text-sm text-ink-muted">
          Вероятности по {formatNumber(simulation.runs, 0)} прогонам, в скобках 95% интервал средней
          позиции. Стрелка открывает сравнение стратегий пилота.
        </p>
        <div className="mt-4">
          <DataTable
            caption="Исходы симуляции по пилотам"
            columns={fieldColumns(race)}
            rows={field}
            rowKey={(row) => row.driver.driver_id}
          />
        </div>
        {field.some((row) => row.driver.strategy?.stand_in) && (
          <p className="mt-3 text-xs text-ink-subtle">
            * Пилот сошёл раньше, чем показал свою стратегию; в симуляции у него самая частая
            стратегия финишёров.
          </p>
        )}
      </section>
    </>
  )
}

export function RacesPage() {
  const [params, setParams] = useSearchParams()
  const races = useRaces()
  const raceId = resolveRaceId(params.get('race'), races.data)
  const race = useRace(raceId)
  const simulatable = race.data?.simulatable ?? false
  const simulation = useSimulation(raceId, simulatable)
  const summary = races.data?.find((item) => item.race_id === raceId)

  if (races.isError)
    return (
      <Page>
        <title>Гонки · F1 Strategy Lab</title>
        <ErrorState error={races.error} />
      </Page>
    )
  if (!races.data)
    return (
      <Page>
        <title>Гонки · F1 Strategy Lab</title>
        <Loading label="Калибруем симулятор и загружаем гонки…" />
      </Page>
    )
  if (raceId === undefined) {
    return (
      <Page>
        <title>Гонки · F1 Strategy Lab</title>
        <Notice title="В базе нет гонок">
          Загрузите данные: <code className="font-mono">python -m f1lab.ingest</code>.
        </Notice>
      </Page>
    )
  }

  return (
    <Page>
      <title>Гонки · F1 Strategy Lab</title>
      <PageHeader
        eyebrow={summary ? `Гонки · ${summary.season} · этап ${summary.round}` : 'Гонки'}
        title={summary?.race_name ?? 'Гонка'}
        description={
          summary &&
          `${summary.circuit_name}${summary.country ? `, ${summary.country}` : ''} · ${formatDate(summary.date)}${
            race.data
              ? ` · ${race.data.race_laps} ${pluralize(race.data.race_laps, ['круг', 'круга', 'кругов'])}`
              : ''
          }`
        }
        aside={
          summary &&
          (summary.in_sample ? (
            <Badge>в выборке калибровки</Badge>
          ) : (
            <Badge tone="success">прогноз вне выборки</Badge>
          ))
        }
      />

      <RacePicker
        races={races.data}
        value={raceId}
        onChange={(next) => setParams({ race: String(next) })}
      />

      {race.isError && <ErrorState error={race.error} />}
      {race.data && !simulatable && (
        <Notice title="Эту гонку симулятор не считает">
          {describeSetupReason(race.data.reason)}. Выберите другую гонку сезона.
        </Notice>
      )}
      {simulation.isError && <ErrorState error={simulation.error} />}
      {simulatable && !simulation.data && !simulation.isError && (
        <Loading label="Считаем симуляцию гонки…" />
      )}
      {race.data && simulation.data && simulation.data.race_id === race.data.race_id && (
        <SimulatedRace race={race.data} simulation={simulation.data} />
      )}
    </Page>
  )
}
