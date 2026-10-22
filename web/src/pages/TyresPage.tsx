import { useSearchParams } from 'react-router'
import { useCircuits, useRaces, useTyres } from '../api/queries'
import type { CircuitSummary, TyreCompound, TyreModel } from '../api/types'
import { ChartCard } from '../charts/ChartCard'
import { type Column, DataTable } from '../charts/DataTable'
import { DegradationChart } from '../charts/DegradationChart'
import { Legend } from '../charts/Legend'
import { COMPOUND_ORDER, COMPOUND_SERIES } from '../charts/series'
import { SlopeDotPlot, type SlopeRow } from '../charts/SlopeDotPlot'
import { Badge, Page, PageHeader } from '../components/PageHeader'
import { Select } from '../components/Select'
import { StatTile } from '../components/StatTile'
import { ErrorState, Loading, Notice } from '../components/States'
import { compoundLabel } from '../data/compounds'
import { slopeRows } from '../lib/rows'
import { resolveCircuitId } from '../lib/selection'
import { formatInterval, formatNumber, formatSigned, pluralize } from '../lib/format'

const SLOPE_UNIT = 'с/круг'

function byCompound(a: { compound: string }, b: { compound: string }): number {
  return (
    COMPOUND_ORDER.indexOf(a.compound as (typeof COMPOUND_ORDER)[number]) -
    COMPOUND_ORDER.indexOf(b.compound as (typeof COMPOUND_ORDER)[number])
  )
}

const CURVE_COLUMNS: readonly Column<{ compound: TyreCompound; age: number }>[] = [
  { key: 'compound', header: 'Состав', cell: (row) => compoundLabel(row.compound.compound) },
  { key: 'age', header: 'Возраст, кр.', numeric: true, cell: (row) => row.age },
  {
    key: 'model',
    header: 'Модель, с',
    numeric: true,
    cell: (row) => formatSigned(row.compound.curve[row.age]?.delta_s ?? 0),
  },
  {
    key: 'observed',
    header: 'Факт, с (кругов)',
    numeric: true,
    cell: (row) => {
      const point = row.compound.observed.find((item) => item.age === row.age)
      return point ? `${formatSigned(point.delta_s)} (${point.laps})` : '—'
    },
  },
]

function TyreKpis({ model }: { model: TyreModel }) {
  return (
    <dl className="grid grid-cols-2 gap-3 lg:grid-cols-4">
      {[...model.compounds].sort(byCompound).map((compound) => (
        <StatTile
          key={compound.compound}
          label={`${compoundLabel(compound.compound)}: деградация`}
          value={formatSigned(compound.degradation_s_per_lap.value, 3)}
          unit={SLOPE_UNIT}
          hint={`95%: ${formatInterval(compound.degradation_s_per_lap.low, compound.degradation_s_per_lap.high, 3)}; шины до ${compound.max_tyre_age} кр. в данных`}
        />
      ))}
      <StatTile
        label="Топливо и трасса"
        value={formatSigned(model.fuel_s_per_lap.value, 3)}
        unit={SLOPE_UNIT}
        hint="машина легчает, трасса резинится: каждый круг быстрее"
      />
    </dl>
  )
}

function CircuitComparison({
  circuits,
  circuitId,
}: {
  circuits: readonly CircuitSummary[]
  circuitId: string
}) {
  const facets = COMPOUND_ORDER.filter((compound) =>
    circuits.some((circuit) => compound in circuit.degradation_s_per_lap),
  ).map((compound) => ({ id: compound, label: compoundLabel(compound) }))
  const rows = slopeRows(circuits)
  const columns: Column<SlopeRow>[] = [
    { key: 'circuit', header: 'Трасса', cell: (row) => row.label },
    ...facets.map((facet) => ({
      key: facet.id,
      header: `${facet.label}, ${SLOPE_UNIT}`,
      numeric: true,
      cell: (row: SlopeRow) => {
        const slope = row.values[facet.id]
        return slope
          ? `${formatNumber(slope.value, 3)} ${formatInterval(slope.low, slope.high, 3)}`
          : '—'
      },
    })),
  ]
  return (
    <ChartCard
      title="Деградация по трассам"
      description="Сколько секунд за круг теряет шина с каждым кругом пробега: точка — оценка, отрезок — 95% интервал. Наклоны частично объединены между трассами (эмпирический Байес), поэтому у трасс с малым числом кругов они ближе к среднему."
      table={
        <DataTable
          caption="Деградация по трассам"
          columns={columns}
          rows={rows}
          rowKey={(row) => row.id}
        />
      }
      footnote="Трассы отсортированы по средней деградации; выбранная выделена цветом составов. Пустая клетка — у трассы мало кругов на этом составе."
    >
      <SlopeDotPlot rows={rows} facets={facets} highlight={circuitId} unit={SLOPE_UNIT} />
    </ChartCard>
  )
}

export function TyresPage() {
  const [params, setParams] = useSearchParams()
  const circuits = useCircuits()
  const races = useRaces()
  const race = races.data?.find((item) => String(item.race_id) === params.get('race'))
  const circuitId = circuits.data
    ? resolveCircuitId(params.get('circuit'), race?.circuit_id, circuits.data)
    : undefined
  const tyres = useTyres(circuitId)
  const model = tyres.data?.circuit_id === circuitId ? tyres.data : undefined

  if (circuits.isError)
    return (
      <Page>
        <title>Шины · F1 Strategy Lab</title>
        <ErrorState error={circuits.error} />
      </Page>
    )
  if (!circuits.data)
    return (
      <Page>
        <title>Шины · F1 Strategy Lab</title>
        <Loading label="Калибруем модель шин…" />
      </Page>
    )
  if (!circuitId) {
    return (
      <Page>
        <title>Шины · F1 Strategy Lab</title>
        <Notice title="Нет моделей шин">
          Загрузите данные: <code className="font-mono">python -m f1lab.ingest</code>.
        </Notice>
      </Page>
    )
  }
  const compounds = model ? [...model.compounds].sort(byCompound) : []

  return (
    <Page>
      <title>Шины · F1 Strategy Lab</title>
      <PageHeader
        eyebrow="Шины"
        title={model?.circuit_name ?? 'Модель шин'}
        description="Регрессия по чистым кругам: уровень пилота в гонке, топливо, сдвиг состава и деградация с возрастом шины. Круги под SC/VSC, мокрые, круги въезда и выезда с пит-лейна отброшены."
        aside={
          model && (
            <>
              <Badge>сезоны {model.seasons.join('–')}</Badge>
              <Badge>
                {formatNumber(model.laps, 0)} {pluralize(model.laps, ['круг', 'круга', 'кругов'])}
              </Badge>
            </>
          )
        }
      />

      <Select
        label="Трасса"
        value={circuitId}
        onChange={(next) => setParams({ circuit: next })}
        className="w-full sm:w-96"
        options={circuits.data.map((circuit) => ({
          value: circuit.circuit_id,
          label: `${circuit.circuit_name}${circuit.country ? ` · ${circuit.country}` : ''}`,
        }))}
      />

      {tyres.isError && <ErrorState error={tyres.error} />}
      {!model && !tyres.isError && <Loading label="Загружаем модель трассы…" />}
      {model && (
        <>
          <TyreKpis model={model} />
          <ChartCard
            title="Время круга и возраст шины"
            description={`Разница со свежим ${compoundLabel(model.reference_compound)} без учёта топлива и уровня пилота. Линия — модель, полоса — 95% интервал наклона, маркеры — средний чистый круг в данных (не меньше 5 кругов на точку).`}
            busy={tyres.isFetching}
            legend={
              <Legend
                items={compounds.map((compound) => {
                  const style = COMPOUND_SERIES[compound.compound]
                  return {
                    label: compoundLabel(compound.compound),
                    key: {
                      kind: 'line',
                      swatch: style.swatch,
                      marker: { shape: style.marker, fill: style.fill },
                    },
                  }
                })}
              />
            }
            table={
              <DataTable
                caption="Модель и средние круги по возрасту шины"
                columns={CURVE_COLUMNS}
                rows={compounds.flatMap((compound) =>
                  compound.curve.map((point) => ({ compound, age: point.age })),
                )}
                rowKey={(row) => `${row.compound.compound}-${row.age}`}
              />
            }
            footnote="Модель не продлевает износ дальше самой старой шины в данных: после неё темп считается постоянным. Составы без истории на трассе симулятор берёт медианой по всем трассам."
          >
            <DegradationChart compounds={compounds} />
          </ChartCard>
          <CircuitComparison circuits={circuits.data} circuitId={circuitId} />
        </>
      )}
    </Page>
  )
}
