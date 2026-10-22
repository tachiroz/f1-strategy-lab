import { scaleLinear } from 'd3-scale'
import { useState } from 'react'
import type { Interval } from '../api/types'
import { formatInterval, formatNumber } from '../lib/format'
import { Marker } from './Marker'
import { COMPOUND_SERIES } from './series'
import { Tooltip, TooltipRow } from './Tooltip'
import { useElementWidth } from './useElementWidth'

export interface SlopeRow {
  id: string
  label: string
  /** Estimate per facet (compound); a missing key leaves the cell empty. */
  values: Readonly<Record<string, Interval>>
}

interface SlopeDotPlotProps {
  rows: readonly SlopeRow[]
  facets: readonly { id: string; label: string }[]
  /** The row the page is about; the others are context in grey. */
  highlight?: string
  unit: string
}

const MARGIN = { top: 44, right: 8, bottom: 8 }
const LABEL_WIDTH = { wide: 176, narrow: 104 }
const NARROW_WIDTH = 560
const FACET_GAP = 28
/** Tick labels closer than this to a panel edge would touch the next panel's labels. */
const EDGE_LABEL_PX = 14
/** Narrower panels only label the zero line. */
const MIN_LABELLED_FACET_PX = 120
const ROW_HEIGHT = 22
const X_TICKS = 3

/**
 * Small multiples, one panel per compound with a shared x scale: estimate and 95% interval
 * per row (circuit). The highlighted row wears the compound colour, the rest stays grey.
 */
export function SlopeDotPlot({ rows, facets, highlight, unit }: SlopeDotPlotProps) {
  const [containerRef, width] = useElementWidth<HTMLDivElement>()
  const [active, setActive] = useState<number | null>(null)
  const narrow = width < NARROW_WIDTH
  const labelWidth = narrow ? LABEL_WIDTH.narrow : LABEL_WIDTH.wide
  const maxChars = narrow ? 13 : 24
  const height = MARGIN.top + rows.length * ROW_HEIGHT + MARGIN.bottom
  const facetWidth =
    (width - labelWidth - MARGIN.right - FACET_GAP * (facets.length - 1)) /
    Math.max(facets.length, 1)
  const intervals = rows.flatMap((row) => Object.values(row.values))
  const x = scaleLinear()
    .domain([
      Math.min(0, ...intervals.map((value) => value.low)),
      Math.max(0, ...intervals.map((value) => value.high)),
    ])
    .nice(X_TICKS)
    .range([0, facetWidth])
  const facetLeft = (index: number) => labelWidth + index * (facetWidth + FACET_GAP)
  const rowY = (index: number) => MARGIN.top + index * ROW_HEIGHT + ROW_HEIGHT / 2
  const activeRow = active === null ? undefined : rows[active]
  const shorten = (label: string) =>
    label.length > maxChars ? `${label.slice(0, maxChars - 1)}…` : label

  return (
    <div ref={containerRef} className="relative">
      <svg
        width={width}
        height={height}
        role="img"
        aria-label="Деградация по трассам и составам с 95% интервалами"
        className="block font-mono text-[11px]"
        onPointerLeave={() => setActive(null)}
      >
        {facets.map((facet, facetIndex) => (
          <g key={facet.id} transform={`translate(${facetLeft(facetIndex)},0)`} aria-hidden="true">
            <text x={0} y={14} className="fill-ink-muted font-sans text-xs">
              {facet.label}
            </text>
            {x.ticks(X_TICKS).map((tick) => (
              <g key={tick}>
                <line
                  x1={x(tick)}
                  x2={x(tick)}
                  y1={MARGIN.top - 6}
                  y2={height - MARGIN.bottom}
                  className={tick === 0 ? 'stroke-line-strong' : 'stroke-line'}
                />
                {(facetWidth >= MIN_LABELLED_FACET_PX
                  ? x(tick) > EDGE_LABEL_PX && x(tick) < facetWidth - EDGE_LABEL_PX
                  : tick === 0) && (
                  <text
                    x={x(tick)}
                    y={MARGIN.top - 12}
                    textAnchor="middle"
                    className="fill-ink-subtle tabular-nums"
                  >
                    {formatNumber(tick, 2)}
                  </text>
                )}
              </g>
            ))}
          </g>
        ))}

        {rows.map((row, index) => {
          const y = rowY(index)
          const emphasised = row.id === highlight
          return (
            <g key={row.id} onPointerEnter={() => setActive(index)}>
              <rect
                x={0}
                y={y - ROW_HEIGHT / 2}
                width={width}
                height={ROW_HEIGHT}
                rx={4}
                className={
                  active === index || emphasised ? 'fill-white/[0.05]' : 'fill-transparent'
                }
              />
              <text
                x={labelWidth - 12}
                y={y}
                dy="0.35em"
                textAnchor="end"
                className={`font-sans ${emphasised ? 'fill-ink font-medium' : 'fill-ink-subtle'}`}
              >
                {shorten(row.label)}
              </text>
              {facets.map((facet, facetIndex) => {
                const value = row.values[facet.id]
                if (!value) return null
                const style = COMPOUND_SERIES[facet.id]
                const left = facetLeft(facetIndex)
                return (
                  <g key={facet.id}>
                    <line
                      x1={left + x(value.low)}
                      x2={left + x(value.high)}
                      y1={y}
                      y2={y}
                      className={`${emphasised ? style.stroke : 'stroke-ink-subtle/50'} [stroke-width:2px] [stroke-linecap:round]`}
                    />
                    <Marker
                      shape={style.marker}
                      x={left + x(value.value)}
                      y={y}
                      size={emphasised ? 4.5 : 3}
                      className={emphasised ? style.fill : 'fill-ink-subtle'}
                    />
                  </g>
                )
              })}
            </g>
          )
        })}
      </svg>

      {activeRow && (
        <Tooltip
          x={labelWidth}
          y={rowY(active ?? 0) + ROW_HEIGHT / 2}
          containerWidth={width}
          title={`${activeRow.label}, ${unit}`}
        >
          {facets.map((facet) => {
            const value = activeRow.values[facet.id]
            return (
              <TooltipRow
                key={facet.id}
                label={facet.label}
                value={
                  value
                    ? `${formatNumber(value.value, 3)} ${formatInterval(value.low, value.high, 3)}`
                    : 'нет модели'
                }
                swatch={COMPOUND_SERIES[facet.id]?.swatch}
              />
            )
          })}
        </Tooltip>
      )}
    </div>
  )
}
