import type { ReactNode } from 'react'

const OFFSET = 14
const TOOLTIP_WIDTH = 232

interface TooltipProps {
  /** Anchor inside the chart container, in px. */
  x: number
  y: number
  containerWidth: number
  title: ReactNode
  children: ReactNode
}

/** Floating readout next to the pointer; flips to the left near the right edge. */
export function Tooltip({ x, y, containerWidth, title, children }: TooltipProps) {
  const flip = x + OFFSET + TOOLTIP_WIDTH > containerWidth
  const left = flip ? Math.max(0, x - OFFSET - TOOLTIP_WIDTH) : x + OFFSET
  return (
    <div
      role="tooltip"
      style={{ left, top: Math.max(0, y), width: TOOLTIP_WIDTH }}
      className="pointer-events-none absolute z-10 rounded-lg border border-line-strong bg-canvas/95 px-3 py-2.5 text-xs shadow-xl shadow-black/40 backdrop-blur"
    >
      <p className="font-medium text-ink">{title}</p>
      <dl className="mt-1.5 space-y-1">{children}</dl>
    </div>
  )
}

interface TooltipRowProps {
  label: ReactNode
  value: ReactNode
  /** Short line key in the series colour (tooltip rows key with a stroke, not a box). */
  swatch?: string
}

/** One readout line: the value leads, the series name follows. */
export function TooltipRow({ label, value, swatch }: TooltipRowProps) {
  return (
    <div className="flex items-baseline gap-2">
      {swatch && (
        <span
          aria-hidden="true"
          className={`h-0.5 w-3 shrink-0 self-center rounded-full ${swatch}`}
        />
      )}
      {/* dt must precede dd in the DOM; the value is shown first with flex order. */}
      <dt className="order-2 min-w-0 truncate text-ink-subtle">{label}</dt>
      <dd className="order-1 font-mono font-medium text-ink tabular-nums">{value}</dd>
    </div>
  )
}
