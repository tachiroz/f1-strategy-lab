/**
 * Visual identity of chart series. Tailwind classes are spelled out in full so they are
 * detected; strategy slots follow a fixed order and never cycle (at most three series).
 */

export type MarkerShape = 'circle' | 'square' | 'diamond'

export interface SeriesStyle {
  stroke: string
  fill: string
  /** Background class for HTML swatches and line keys. */
  swatch: string
  /** Second channel next to colour, so identity never depends on hue alone. */
  marker: MarkerShape
}

export const STRATEGY_SERIES: readonly SeriesStyle[] = [
  { stroke: 'stroke-series-1', fill: 'fill-series-1', swatch: 'bg-series-1', marker: 'circle' },
  { stroke: 'stroke-series-2', fill: 'fill-series-2', swatch: 'bg-series-2', marker: 'square' },
  { stroke: 'stroke-series-3', fill: 'fill-series-3', swatch: 'bg-series-3', marker: 'diamond' },
]

/** Letters that name the strategies in charts, legends and cards. */
export const STRATEGY_LETTERS = ['Ф', 'A', 'B'] as const

/** Pirelli colours for dry compounds, with the marker shapes used in the Python charts. */
export const COMPOUND_SERIES: Readonly<Record<string, SeriesStyle>> = {
  SOFT: {
    stroke: 'stroke-tyre-soft',
    fill: 'fill-tyre-soft',
    swatch: 'bg-tyre-soft',
    marker: 'circle',
  },
  MEDIUM: {
    stroke: 'stroke-tyre-medium',
    fill: 'fill-tyre-medium',
    swatch: 'bg-tyre-medium',
    marker: 'square',
  },
  HARD: {
    stroke: 'stroke-tyre-hard',
    fill: 'fill-tyre-hard',
    swatch: 'bg-tyre-hard',
    marker: 'diamond',
  },
}

export const COMPOUND_ORDER = ['SOFT', 'MEDIUM', 'HARD'] as const

export function strategySeries(index: number): SeriesStyle {
  const style = STRATEGY_SERIES[index]
  if (!style) throw new Error(`No series style for strategy #${index + 1}`)
  return style
}
