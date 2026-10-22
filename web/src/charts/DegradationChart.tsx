import { scaleLinear } from 'd3-scale'
import { area, line } from 'd3-shape'
import { Fragment, type KeyboardEvent, useState } from 'react'
import type { CurvePoint, TyreCompound } from '../api/types'
import { compoundLabel } from '../data/compounds'
import { formatSigned } from '../lib/format'
import { dodgeLabels, localPoint } from './geometry'
import { Marker } from './Marker'
import { COMPOUND_SERIES } from './series'
import { Tooltip, TooltipRow } from './Tooltip'
import { useElementWidth } from './useElementWidth'

interface DegradationChartProps {
  compounds: readonly TyreCompound[]
}

const MARGIN = { top: 16, right: 72, bottom: 40, left: 52 }
const PLOT_HEIGHT = 300
const Y_TICKS = 6
const X_TICKS = 8
const LABEL_GAP = 14
const OBSERVED_MARKER = 3.5

/**
 * Lap time against tyre age for every compound: model line with the interval of its
 * degradation slope (band) and the observed mean clean-lap delta (markers).
 */
export function DegradationChart({ compounds }: DegradationChartProps) {
  const [containerRef, width] = useElementWidth<HTMLDivElement>()
  const [age, setAge] = useState<number | null>(null)
  const maxAge = Math.max(1, ...compounds.map((compound) => compound.max_tyre_age))
  const values = compounds.flatMap((compound) => [
    ...compound.curve.flatMap((point) => [point.low, point.high]),
    ...compound.observed.map((point) => point.delta_s),
  ])
  const x = scaleLinear()
    .domain([0, maxAge])
    .range([MARGIN.left, width - MARGIN.right])
  const y = scaleLinear()
    .domain([Math.min(0, ...values), Math.max(0, ...values)])
    .nice(Y_TICKS)
    .range([MARGIN.top + PLOT_HEIGHT, MARGIN.top])
  const height = MARGIN.top + PLOT_HEIGHT + MARGIN.bottom
  const toLine = line<CurvePoint>()
    .x((point) => x(point.age))
    .y((point) => y(point.delta_s))
  const toBand = area<CurvePoint>()
    .x((point) => x(point.age))
    .y0((point) => y(point.low))
    .y1((point) => y(point.high))
  const ends = compounds.map((compound) => {
    const last = compound.curve[compound.curve.length - 1]
    return { id: compound.compound, x: x(last.age), y: y(last.delta_s) }
  })
  const labelY = dodgeLabels(ends, LABEL_GAP, MARGIN.top, MARGIN.top + PLOT_HEIGHT)

  function moveAge(event: KeyboardEvent) {
    const step = event.key === 'ArrowRight' ? 1 : event.key === 'ArrowLeft' ? -1 : 0
    if (!step) return
    event.preventDefault()
    setAge((current) => Math.min(maxAge, Math.max(0, (current ?? 0) + step)))
  }

  return (
    <div ref={containerRef} className="relative">
      <svg
        width={width}
        height={height}
        role="img"
        aria-label="Деградация шин: время круга в зависимости от возраста шины"
        className="block font-mono text-[11px] outline-none"
        tabIndex={0}
        onKeyDown={moveAge}
        onBlur={() => setAge(null)}
        onPointerLeave={() => setAge(null)}
        onPointerMove={(event) => {
          const { x: px } = localPoint(event, event.currentTarget)
          if (px < MARGIN.left || px > width - MARGIN.right) return setAge(null)
          setAge(Math.round(x.invert(px)))
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
                x={MARGIN.left - 8}
                y={y(tick)}
                dy="0.35em"
                textAnchor="end"
                className="fill-ink-subtle tabular-nums"
              >
                {formatSigned(tick, 1)}
              </text>
            </g>
          ))}
          {x.ticks(X_TICKS).map((tick) => (
            <text
              key={tick}
              x={x(tick)}
              y={MARGIN.top + PLOT_HEIGHT + 18}
              textAnchor="middle"
              className="fill-ink-subtle tabular-nums"
            >
              {tick}
            </text>
          ))}
          <text
            x={(MARGIN.left + width - MARGIN.right) / 2}
            y={height - 4}
            textAnchor="middle"
            className="fill-ink-subtle font-sans"
          >
            Возраст шины, кругов
          </text>
        </g>

        {compounds.map((compound) => {
          const style = COMPOUND_SERIES[compound.compound]
          return (
            <g key={compound.compound}>
              <path d={toBand(compound.curve) ?? ''} className={`${style.fill} opacity-10`} />
              {compound.observed.map((point) => (
                <Marker
                  key={point.age}
                  shape={style.marker}
                  x={x(point.age)}
                  y={y(point.delta_s)}
                  size={OBSERVED_MARKER}
                  className={`${style.fill} opacity-80`}
                />
              ))}
              <path
                d={toLine(compound.curve) ?? ''}
                className={`fill-none ${style.stroke} [stroke-width:2px] [stroke-linecap:round] [stroke-linejoin:round]`}
              />
            </g>
          )
        })}

        <g aria-hidden="true">
          {ends.map((end) => {
            const placed = labelY.get(end.id) ?? end.y
            return (
              <g key={end.id}>
                {Math.abs(placed - end.y) > 2 && (
                  <line
                    x1={end.x + 3}
                    y1={end.y}
                    x2={end.x + 10}
                    y2={placed}
                    className="stroke-ink-subtle"
                  />
                )}
                <text x={end.x + 12} y={placed} dy="0.35em" className="fill-ink-muted font-sans">
                  {compoundLabel(end.id)}
                </text>
              </g>
            )
          })}
        </g>

        {age !== null && (
          <line
            x1={x(age)}
            x2={x(age)}
            y1={MARGIN.top}
            y2={MARGIN.top + PLOT_HEIGHT}
            className="stroke-ink-subtle"
          />
        )}
      </svg>

      {age !== null && (
        <Tooltip
          x={x(age)}
          y={MARGIN.top}
          containerWidth={width}
          title={`Шина возрастом ${age} кр.`}
        >
          {compounds.map((compound) => {
            const point = compound.curve.find((p) => p.age === age)
            const observed = compound.observed.find((p) => p.age === age)
            const style = COMPOUND_SERIES[compound.compound]
            return (
              <Fragment key={compound.compound}>
                <TooltipRow
                  label={`${compoundLabel(compound.compound)}, модель`}
                  value={point ? `${formatSigned(point.delta_s)} с` : 'нет данных'}
                  swatch={style.swatch}
                />
                {observed && (
                  <TooltipRow
                    label={`факт, ${observed.laps} кр.`}
                    value={`${formatSigned(observed.delta_s)} с`}
                  />
                )}
              </Fragment>
            )
          })}
        </Tooltip>
      )}
    </div>
  )
}
