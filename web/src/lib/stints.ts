/** Stint helpers shared by the strategy bars and editors. */
import type { Stint } from '../api/types'
import { compoundLabel } from '../data/compounds'

/** Width of one character of the 11px mono label, and the segment's inner padding. */
const CHAR_PX = 7
const LABEL_PADDING_PX = 16
export const SEGMENT_GAP_PX = 2

export function stintLaps(stint: Stint): number {
  return stint.last_lap - stint.first_lap + 1
}

export function describeStints(stints: readonly Stint[]): string {
  return stints
    .map((stint) => `${compoundLabel(stint.compound)}, круги ${stint.first_lap}–${stint.last_lap}`)
    .join('; ')
}

/** The longest label that fits a segment of `widthPx` without clipping ('' if none fits). */
export function stintLabel(name: string, laps: number, widthPx: number): string {
  const candidates = [`${name} · ${laps}`, `${name.charAt(0)} · ${laps}`, name.charAt(0)]
  return candidates.find((text) => text.length * CHAR_PX + LABEL_PADDING_PX <= widthPx) ?? ''
}
