import { scaleBand, scaleLinear } from 'd3-scale'
import { useState } from 'react'
import { formatPercent } from '../lib/format'
import { BAR_GAP, columnPath, localPoint, MAX_BAR_WIDTH } from './geometry'
import type { SeriesStyle } from './series'
import { Tooltip, TooltipRow } from './Tooltip'
import { useElementWidth } from './useElementWidth'

export interface HistogramSeries {
  id: string
  label: string
  /** Shares for positions 1..fieldSize followed by the share of retirements. */
  values: readonly number[]
  style: SeriesStyle
}

interface PositionHistogramProps {
  series: readonly HistogramSeries[]
  fieldSize: number
}

const MARGIN = { top: 12, right: 8, bottom: 28, left: 40 }
const PLOT_HEIGHT = 220
const Y_TICKS = 4
const GAP_KEY = 'gap'
const RETIRED_KEY = 'dnf'
const MIN_LABEL_BAND = 18
const SPARSE_LABELS = new Set(['1', '5', '10', '15', '20'])

/** Grouped columns: share of runs ending in each position (and in retirement), per strategy. */
export function PositionHistogram({ series, fieldSize }: PositionHistogramProps) {
  const [containerRef, width] = useElementWidth<HTMLDivElement>()
  const [active, setActive] = useState<number | null>(null)
  const positions = Array.from({ length: fieldSize }, (_, index) => String(index + 1))
  const categories = [...positions, GAP_KEY, RETIRED_KEY]
  const x = scaleBand<string>()
    .domain(categories)
    .range([MARGIN.left, width - MARGIN.right])
    .paddingInner(0.2)
    .paddingOuter(0.05)
  const maxShare = Math.max(0.01, ...series.flatMap((s) => s.values))
  const y = scaleLinear()
    .domain([0, maxShare])
    .nice(Y_TICKS)
    .range([MARGIN.top + PLOT_HEIGHT, MARGIN.top])
  const height = MARGIN.top + PLOT_HEIGHT + MARGIN.bottom
  const barWidth = Math.min(
    MAX_BAR_WIDTH,
    (x.bandwidth() - BAR_GAP * (series.length - 1)) / Math.max(series.length, 1),
  )
  const groupWidth = barWidth * series.length + BAR_GAP * (series.length - 1)
  const valueIndex = (category: string) =>
    category === RETIRED_KEY ? fieldSize : Number(category) - 1
  const showAllLabels = x.bandwidth() >= MIN_LABEL_BAND
  const dataCategories = [...positions, RETIRED_KEY]
  const activeCategory = active === null ? undefined : dataCategories[active]

  function categoryLabel(category: string) {
    return category === RETIRED_KEY ? 'Сход' : `P${category}`
  }

  return (
    <div ref={containerRef} className="relative">
      <svg
        width={width}
        height={height}
        role="img"
        aria-label="Распределение финишной позиции по стратегиям"
        className="block font-mono text-[11px]"
        onPointerLeave={() => setActive(null)}
        onPointerMove={(event) => {
          const { x: px } = localPoint(event, event.currentTarget)
          const index = dataCategories.findIndex((category) => {
            const start = x(category) ?? 0
            const step = x.step()
            return (
              px >= start - (step - x.bandwidth()) / 2 &&
              px < start + x.bandwidth() + (step - x.bandwidth()) / 2
            )
          })
          setActive(index >= 0 ? index : null)
        }}
      >
        <g aria-hidden="true">
          {y.ticks(Y_TICKS).map((tick) => (
            <g key={tick}>
              <line
                x1={MARGIN.left}
                x2={width - MARGIN.right}
                y1={y(tick)}
                y2={y(tick)}
                className={tick === 0 ? 'stroke-line-strong' : 'stroke-line'}
              />
              <text
                x={MARGIN.left - 6}
                y={y(tick)}
                dy="0.35em"
                textAnchor="end"
                className="fill-ink-subtle tabular-nums"
              >
                {formatPercent(tick)}
              </text>
            </g>
          ))}
        </g>

        {activeCategory !== undefined && (
          <rect
            x={(x(activeCategory) ?? 0) - (x.step() - x.bandwidth()) / 2}
            y={MARGIN.top}
            width={x.step()}
            height={PLOT_HEIGHT}
            rx={4}
            className="fill-white/[0.05]"
          />
        )}

        {dataCategories.map((category) => {
          const left = (x(category) ?? 0) + (x.bandwidth() - groupWidth) / 2
          return (
            <g key={category}>
              {series.map((item, index) => {
                const share = item.values[valueIndex(category)] ?? 0
                if (share <= 0) return null
                const top = y(share)
                return (
                  <path
                    key={item.id}
                    d={columnPath(left + index * (barWidth + BAR_GAP), top, barWidth, y(0) - top)}
                    className={item.style.fill}
                  />
                )
              })}
              {(showAllLabels || SPARSE_LABELS.has(category) || category === RETIRED_KEY) && (
                <text
                  x={(x(category) ?? 0) + x.bandwidth() / 2}
                  y={MARGIN.top + PLOT_HEIGHT + 18}
                  textAnchor="middle"
                  className={category === RETIRED_KEY ? 'fill-ink-muted' : 'fill-ink-subtle'}
                >
                  {category === RETIRED_KEY ? 'Сход' : category}
                </text>
              )}
            </g>
          )
        })}
      </svg>

      {activeCategory !== undefined && (
        <Tooltip
          x={(x(activeCategory) ?? 0) + x.bandwidth() / 2}
          y={MARGIN.top + PLOT_HEIGHT / 3}
          containerWidth={width}
          title={categoryLabel(activeCategory)}
        >
          {series.map((item) => (
            <TooltipRow
              key={item.id}
              label={item.label}
              value={formatPercent(item.values[valueIndex(activeCategory)] ?? 0)}
              swatch={item.style.swatch}
            />
          ))}
        </Tooltip>
      )}
    </div>
  )
}
