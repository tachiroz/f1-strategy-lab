import type { RaceDetail, RaceSimulation } from '../api/types'
import { POINTS_POSITIONS } from '../config'
import { formatGrid, formatNumber } from '../lib/format'
import { outcomeRows } from '../lib/rows'
import { ChartCard } from './ChartCard'
import { type Column, DataTable } from './DataTable'
import { Legend } from './Legend'
import { OutcomeChart, type OutcomeRow } from './OutcomeChart'

const OUTCOME_COLUMNS: readonly Column<OutcomeRow>[] = [
  { key: 'driver', header: 'Пилот', cell: (row) => `${row.code} · ${row.name}` },
  { key: 'grid', header: 'Старт', numeric: true, cell: (row) => formatGrid(row.grid) },
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

/** "Forecast against the result" card: the simulated band per driver next to the real finish. */
export function OutcomeCard({
  race,
  simulation,
}: {
  race: RaceDetail
  simulation: RaceSimulation
}) {
  const rows = outcomeRows(race, simulation)
  return (
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
  )
}
