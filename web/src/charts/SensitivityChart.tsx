import { scaleLinear, scalePoint } from 'd3-scale'
import { line } from 'd3-shape'
import { Fragment, type KeyboardEvent, useState } from 'react'
import type { SensitivityPoint } from '../api/types'
import { formatInterval, formatNumber, formatPercent, formatScale } from '../lib/format'
import { dodgeLabels, localPoint } from './geometry'
import { Marker } from './Marker'
import type { SeriesStyle } from './series'
import { Tooltip, TooltipRow } from './Tooltip'
import { useElementWidth } from './useElementWidth'

export interface SensitivityLine {
  id: string
  /** Short name drawn at the end of the line (a strategy letter). */
  tag: string
  label: string
  points: readonly SensitivityPoint[]
  style: SeriesStyle
}

interface SensitivityChartProps {
  lines: readonly SensitivityLine[]
  scales: readonly number[]
}

const MARGIN = { top: 28, right: 36, bottom: 48, left: 48 }
const PLOT_HEIGHT = 240
const Y_TICKS = 5
const LABEL_GAP = 14
const HISTORY_SCALE = 1
const Y_PADDING = 0.15

/**
 * Mean finishing position of each strategy as Safety Cars become rarer or more frequent
 * than the circuit's history. Better positions are drawn higher.
 */
export function SensitivityChart({ lines, scales }: SensitivityChartProps) {
  const [containerRef, width] = useElementWidth<HTMLDivElement>()
  const [active, setActive] = useState<number | null>(null)
  const keys = scales.map(String)
  const x = scalePoint<string>()
    .domain(keys)
    .range([MARGIN.left, width - MARGIN.right])
    .padding(0.4)
  const means = lines.flatMap((item) => item.points.map((point) => point.mean_position.value))
  const low = Math.min(...means)
  const high = Math.max(...means)
  const pad = Math.max((high - low) * Y_PADDING, Y_PADDING)
  // Position 1 is the best result: smaller values go to the top.
  const y = scaleLinear()
    .domain([low - pad, high + pad])
    .nice(Y_TICKS)
    .range([MARGIN.top, MARGIN.top + PLOT_HEIGHT])
  const height = MARGIN.top + PLOT_HEIGHT + MARGIN.bottom
  const toLine = line<SensitivityPoint>()
    .x((point) => x(String(point.scale)) ?? 0)
    .y((point) => y(point.mean_position.value))
  const shares = lines[0]?.points.map((point) => point.p_safety_car) ?? []
  const lastKey = keys[keys.length - 1]
  const ends = lines.map((item) => ({
    id: item.id,
    y: y(item.points[item.points.length - 1]?.mean_position.value ?? 0),
  }))
  const labelY = dodgeLabels(ends, LABEL_GAP, MARGIN.top, MARGIN.top + PLOT_HEIGHT)
  const historyX = x(String(HISTORY_SCALE))

  function moveActive(event: KeyboardEvent) {
    const step = event.key === 'ArrowRight' ? 1 : event.key === 'ArrowLeft' ? -1 : 0
    if (!step) return
    event.preventDefault()
    setActive((current) => Math.min(keys.length - 1, Math.max(0, (current ?? -1) + step)))
  }

  return (
    <div ref={containerRef} className="relative">
      <svg
        width={width}
        height={height}
        role="img"
        aria-label="Средняя позиция стратегий при разной частоте Safety Car"
        tabIndex={0}
        className="block font-mono text-[11px] outline-none"
        onKeyDown={moveActive}
        onBlur={() => setActive(null)}
        onPointerLeave={() => setActive(null)}
        onPointerMove={(event) => {
          const { x: px } = localPoint(event, event.currentTarget)
          let nearest = 0
          keys.forEach((key, index) => {
            if (Math.abs((x(key) ?? 0) - px) < Math.abs((x(keys[nearest]) ?? 0) - px))
              nearest = index
          })
          setActive(nearest)
        }}
      >
        <g aria-hidden="true">
          {historyX !== undefined && (
            <>
              <rect
                x={historyX - x.step() / 2}
                y={MARGIN.top}
                width={x.step()}
                height={PLOT_HEIGHT}
                rx={6}
                className="fill-white/[0.03]"
              />
              <text
                x={historyX}
                y={MARGIN.top - 10}
                textAnchor="middle"
                className="fill-ink-subtle font-sans"
              >
                история трассы
              </text>
            </>
          )}
          {y.ticks(Y_TICKS).map((tick) => (
            <g key={tick}>
              <line
                x1={MARGIN.left}
                x2={width - MARGIN.right}
                y1={y(tick)}
                y2={y(tick)}
                className="stroke-line"
              />
              <text
                x={MARGIN.left - 8}
                y={y(tick)}
                dy="0.35em"
                textAnchor="end"
                className="fill-ink-subtle tabular-nums"
              >
                {formatNumber(tick, 1)}
              </text>
            </g>
          ))}
          {keys.map((key, index) => (
            <g key={key}>
              <text
                x={x(key)}
                y={MARGIN.top + PLOT_HEIGHT + 18}
                textAnchor="middle"
                className="fill-ink-muted tabular-nums"
              >
                {formatScale(scales[index])}
              </text>
              <text
                x={x(key)}
                y={MARGIN.top + PLOT_HEIGHT + 34}
                textAnchor="middle"
                className="fill-ink-subtle tabular-nums"
              >
                SC {formatPercent(shares[index] ?? 0)}
              </text>
            </g>
          ))}
        </g>

        {active !== null && (
          <line
            x1={x(keys[active])}
            x2={x(keys[active])}
            y1={MARGIN.top}
            y2={MARGIN.top + PLOT_HEIGHT}
            className="stroke-ink-subtle"
          />
        )}

        {lines.map((item) => (
          <g key={item.id}>
            <path
              d={toLine([...item.points]) ?? ''}
              className={`fill-none ${item.style.stroke} [stroke-width:2px] [stroke-linecap:round] [stroke-linejoin:round]`}
            />
            {item.points.map((point) => (
              <Marker
                key={point.scale}
                shape={item.style.marker}
                x={x(String(point.scale)) ?? 0}
                y={y(point.mean_position.value)}
                className={item.style.fill}
              />
            ))}
            <text
              x={(x(lastKey) ?? 0) + 12}
              y={labelY.get(item.id)}
              dy="0.35em"
              className="fill-ink-muted font-sans"
            >
              {item.tag}
            </text>
          </g>
        ))}
      </svg>

      {active !== null && (
        <Tooltip
          x={x(keys[active]) ?? 0}
          y={MARGIN.top}
          containerWidth={width}
          title={`${formatScale(scales[active])} к истории · SC в ${formatPercent(shares[active] ?? 0)} гонок`}
        >
          {lines.map((item) => {
            const point = item.points[active]
            return (
              <Fragment key={item.id}>
                <TooltipRow
                  label={item.label}
                  value={formatNumber(point.mean_position.value)}
                  swatch={item.style.swatch}
                />
                <TooltipRow
                  label="95% интервал"
                  value={formatInterval(point.mean_position.low, point.mean_position.high)}
                />
                <TooltipRow
                  label="подиум · очки"
                  value={`${formatPercent(point.p_podium)} · ${formatPercent(point.p_points)}`}
                />
              </Fragment>
            )
          })}
        </Tooltip>
      )}
    </div>
  )
}
