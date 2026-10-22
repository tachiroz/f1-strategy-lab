import type { MarkerShape } from './series'

interface MarkerProps {
  shape: MarkerShape
  x: number
  y: number
  /** Half the marker width in px; 4 gives the 8px minimum marker. */
  size?: number
  className?: string
}

/** Data marker with a 2px ring in the surface colour (half of a 4px stroke painted under the fill). */
export function Marker({ shape, x, y, size = 4, className = '' }: MarkerProps) {
  const common = `${className} stroke-surface [stroke-width:4px] [paint-order:stroke]`
  if (shape === 'square') {
    return (
      <rect
        x={x - size}
        y={y - size}
        width={size * 2}
        height={size * 2}
        rx={1.5}
        className={common}
      />
    )
  }
  if (shape === 'diamond') {
    const r = size * Math.SQRT2
    return (
      <path d={`M${x} ${y - r}L${x + r} ${y}L${x} ${y + r}L${x - r} ${y}Z`} className={common} />
    )
  }
  return <circle cx={x} cy={y} r={size} className={common} />
}

/** Marker drawn in a small inline SVG, for legends and tooltips. */
export function MarkerIcon({ shape, className }: { shape: MarkerShape; className: string }) {
  return (
    <svg viewBox="0 0 14 14" aria-hidden="true" className="size-3.5 shrink-0">
      <Marker shape={shape} x={7} y={7} size={4} className={className} />
    </svg>
  )
}
