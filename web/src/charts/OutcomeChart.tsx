import { scaleLinear } from 'd3-scale'
import { useState } from 'react'
import { formatNumber, formatPercent } from '../lib/format'
import { Marker } from './Marker'
import { Tooltip, TooltipRow } from './Tooltip'
import { useElementWidth } from './useElementWidth'

export interface OutcomeRow {
  id: string
  code: string
  name: string
  /** Official grid position, 0 for a pit-lane start. */
  grid: number
  /** Simulated position when the car finishes: mean and 10-90% spread. */
  mean: number | null
  low: number | null
  high: number | null
  /** Real classified position; null if the driver was not classified. */
  actual: number | null
  pRetire: number
}

interface OutcomeChartProps {
  rows: readonly OutcomeRow[]
  fieldSize: number
  pointsPositions: number
}

const MARGIN = { top: 28, right: 44, bottom: 8, left: 48 }
const ROW_HEIGHT = 26
const BAND_HEIGHT = 8
const MIN_BAND_WIDTH = 8
const TICKS = [1, 5, 10, 15, 20]

function gridLabel(grid: number): string {
  return grid === 0 ? 'пит-лейн' : `P${grid}`
}

/**
 * One row per driver: the simulated finishing range (band) and mean (dot) next to the real
 * finish (diamond) and the starting slot (ring), i.e. against the "finish = grid" baseline.
 */
export function OutcomeChart({ rows, fieldSize, pointsPositions }: OutcomeChartProps) {
  const [containerRef, width] = useElementWidth<HTMLDivElement>()
  const [active, setActive] = useState<number | null>(null)
  const height = MARGIN.top + rows.length * ROW_HEIGHT + MARGIN.bottom
  const x = scaleLinear()
    .domain([0.5, fieldSize + 0.5])
    .range([MARGIN.left, width - MARGIN.right])
  const rowY = (index: number) => MARGIN.top + index * ROW_HEIGHT + ROW_HEIGHT / 2
  const ticks = TICKS.filter((tick) => tick <= fieldSize)
  const activeRow = active === null ? undefined : rows[active]

  return (
    <div ref={containerRef} className="relative">
      <svg
        width={width}
        height={height}
        className="block overflow-visible font-mono text-[11px]"
        role="img"
        aria-label="Симулированные и реальные финишные позиции по пилотам"
        onPointerLeave={() => setActive(null)}
      >
        <g aria-hidden="true">
          <rect
            x={x(0.5)}
            y={MARGIN.top - 4}
            width={x(pointsPositions + 0.5) - x(0.5)}
            height={rows.length * ROW_HEIGHT + 8}
            rx={8}
            className="fill-white/[0.025]"
          />
          {ticks.map((tick) => (
            <g key={tick}>
              <line
                x1={x(tick)}
                x2={x(tick)}
                y1={MARGIN.top - 4}
                y2={height - MARGIN.bottom}
                className="stroke-line"
              />
              <text
                x={x(tick)}
                y={MARGIN.top - 12}
                textAnchor="middle"
                className="fill-ink-subtle tabular-nums"
              >
                P{tick}
              </text>
            </g>
          ))}
        </g>

        <g role="list" aria-label="Пилоты">
          {rows.map((row, index) => {
            const y = rowY(index)
            const isActive = active === index
            const bandStart = row.low === null ? null : x(row.low)
            const bandEnd = row.high === null ? null : x(row.high)
            const start = row.grid === 0 ? fieldSize : row.grid
            return (
              <g
                key={row.id}
                role="listitem"
                tabIndex={0}
                aria-label={`${row.name}: в среднем ${
                  row.mean === null ? 'не финиширует' : formatNumber(row.mean, 1)
                }, факт ${row.actual === null ? 'сход' : `P${row.actual}`}`}
                onPointerEnter={() => setActive(index)}
                onFocus={() => setActive(index)}
                onBlur={() => setActive(null)}
                className="outline-none"
              >
                <rect
                  x={0}
                  y={y - ROW_HEIGHT / 2}
                  width={width}
                  height={ROW_HEIGHT}
                  rx={6}
                  className={isActive ? 'fill-white/[0.06]' : 'fill-transparent'}
                />
                <text x={4} y={y} dy="0.35em" className={isActive ? 'fill-ink' : 'fill-ink-muted'}>
                  {row.code}
                </text>
                {bandStart !== null && bandEnd !== null && (
                  <rect
                    x={Math.min(bandStart, (bandStart + bandEnd) / 2 - MIN_BAND_WIDTH / 2)}
                    y={y - BAND_HEIGHT / 2}
                    width={Math.max(bandEnd - bandStart, MIN_BAND_WIDTH)}
                    height={BAND_HEIGHT}
                    rx={BAND_HEIGHT / 2}
                    className="fill-series-1/35"
                  />
                )}
                <circle
                  cx={x(start)}
                  cy={y}
                  r={4}
                  className="fill-none stroke-ink-subtle [stroke-width:1.5px]"
                />
                {row.mean !== null && (
                  <Marker shape="circle" x={x(row.mean)} y={y} className="fill-series-1" />
                )}
                {row.actual !== null ? (
                  <Marker shape="diamond" x={x(row.actual)} y={y} size={3.5} className="fill-ink" />
                ) : (
                  <text
                    x={width - 4}
                    y={y}
                    dy="0.35em"
                    textAnchor="end"
                    className="fill-ink-subtle"
                  >
                    сход
                  </text>
                )}
              </g>
            )
          })}
        </g>
      </svg>

      {activeRow && (
        <Tooltip
          x={activeRow.mean === null ? x(fieldSize / 2) : x(activeRow.mean)}
          y={rowY(active ?? 0) + ROW_HEIGHT / 2}
          containerWidth={width}
          title={`${activeRow.name} · ${activeRow.code}`}
        >
          <TooltipRow
            label="факт"
            value={activeRow.actual === null ? 'сход' : `P${activeRow.actual}`}
          />
          <TooltipRow
            label="среднее в симуляции (при финише)"
            value={activeRow.mean === null ? '—' : formatNumber(activeRow.mean, 1)}
            swatch="bg-series-1"
          />
          {activeRow.low !== null && activeRow.high !== null && (
            <TooltipRow
              label="80% прогонов"
              value={`P${Math.round(activeRow.low)}–P${Math.round(activeRow.high)}`}
            />
          )}
          <TooltipRow label="старт" value={gridLabel(activeRow.grid)} />
          <TooltipRow label="сход в симуляции" value={formatPercent(activeRow.pRetire)} />
        </Tooltip>
      )}
    </div>
  )
}
