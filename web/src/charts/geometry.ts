/** Small geometry helpers shared by the SVG charts. */

/** Corner radius of a bar's data end; the baseline end stays square. */
export const BAR_RADIUS = 4
/** Bars never grow thicker than this; the rest of the band is air. */
export const MAX_BAR_WIDTH = 24
/** Surface-coloured gap between touching bars. */
export const BAR_GAP = 2

/** Path of a column whose top corners are rounded and whose bottom sits on the baseline. */
export function columnPath(x: number, y: number, width: number, height: number): string {
  const r = Math.min(BAR_RADIUS, width / 2, height)
  const bottom = y + height
  return [
    `M${x},${bottom}`,
    `V${y + r}`,
    `Q${x},${y} ${x + r},${y}`,
    `H${x + width - r}`,
    `Q${x + width},${y} ${x + width},${y + r}`,
    `V${bottom}`,
    'Z',
  ].join('')
}

export interface LabelPosition {
  id: string
  y: number
}

/**
 * Spread end-of-line labels so they are at least `minGap` apart, keeping their order and
 * staying within [min, max]. Returns the new y for every id.
 */
export function dodgeLabels(
  labels: readonly LabelPosition[],
  minGap: number,
  min: number,
  max: number,
): Map<string, number> {
  const sorted = [...labels].sort((a, b) => a.y - b.y)
  const placed = sorted.map((label) => ({ ...label }))
  for (let i = 1; i < placed.length; i++) {
    placed[i].y = Math.max(placed[i].y, placed[i - 1].y + minGap)
  }
  const overflow = placed.length ? placed[placed.length - 1].y - max : 0
  if (overflow > 0) {
    placed[placed.length - 1].y -= overflow
    for (let i = placed.length - 2; i >= 0; i--) {
      placed[i].y = Math.min(placed[i].y, placed[i + 1].y - minGap)
    }
  }
  for (const label of placed) label.y = Math.max(label.y, min)
  return new Map(placed.map((label) => [label.id, label.y]))
}

/** Pointer position relative to an element's top-left corner. */
export function localPoint(
  event: { clientX: number; clientY: number },
  element: Element,
): { x: number; y: number } {
  const box = element.getBoundingClientRect()
  return { x: event.clientX - box.left, y: event.clientY - box.top }
}
