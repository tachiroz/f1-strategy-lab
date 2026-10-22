/**
 * Strategy notation, the same rules as src/f1lab/sim/strategy.py, so the editor can
 * explain a mistake and preview the stints before asking the API.
 *
 *   M-25-H         start on new mediums, pit at the end of lap 25 for hards
 *   S3-14-M-32-M   softs with 3 laps of use, stops on laps 14 and 32
 */
import type { Stint } from '../api/types'

export const COMPOUND_BY_LETTER: Readonly<Record<string, string>> = {
  S: 'SOFT',
  M: 'MEDIUM',
  H: 'HARD',
}
/** Sporting rule: a dry race must use at least two different dry compounds. */
export const MIN_DRY_COMPOUNDS = 2

const NOTATION = /^([A-Z])(\d*)((?:-\d+-[A-Z])*)$/

export type ParsedStrategy =
  { ok: true; notation: string; stints: Stint[] } | { ok: false; error: string }

/** Parse and validate a strategy for a race of `raceLaps` laps. */
export function parseStrategy(text: string, raceLaps: number): ParsedStrategy {
  const match = NOTATION.exec(text.trim().toUpperCase())
  if (!match) return { ok: false, error: 'Формат: M-25-H или S3-14-M-32-M' }
  const [, startLetter, startAge, rest] = match
  const tokens = rest.split('-').filter(Boolean)
  const letters = [startLetter, ...tokens.filter((_, index) => index % 2 === 1)]
  const unknown = letters.filter((letter) => !(letter in COMPOUND_BY_LETTER))
  if (unknown.length) {
    return { ok: false, error: `Неизвестный состав: ${unknown.join(', ')}. Есть S, M и H` }
  }
  const laps = tokens.filter((_, index) => index % 2 === 0).map(Number)
  if (laps.some((lap) => lap < 1 || lap >= raceLaps)) {
    return { ok: false, error: `Пит-стоп возможен на кругах с 1 по ${raceLaps - 1}` }
  }
  if (laps.some((lap, index) => index > 0 && lap <= laps[index - 1])) {
    return { ok: false, error: 'Круги пит-стопов должны идти по возрастанию' }
  }
  const compounds = letters.map((letter) => COMPOUND_BY_LETTER[letter])
  if (new Set(compounds).size < MIN_DRY_COMPOUNDS) {
    return { ok: false, error: 'В сухой гонке нужны минимум два разных состава' }
  }
  const age = Number(startAge || 0)
  const notation = [
    `${startLetter}${age ? age : ''}`,
    ...laps.map((lap, i) => `${lap}-${letters[i + 1]}`),
  ]
  const bounds = [0, ...laps, raceLaps]
  return {
    ok: true,
    notation: notation.join('-'),
    stints: compounds.map((compound, index) => ({
      compound,
      first_lap: bounds[index] + 1,
      last_lap: bounds[index + 1],
    })),
  }
}

/** Human-readable reason why a race cannot be simulated. */
export function describeSetupReason(reason: string | null): string {
  if (!reason) return ''
  if (/INTERMEDIATE|WET/.test(reason)) return 'Мокрая гонка: симулятор считает только сухие'
  if (reason.includes('UNKNOWN')) return 'В данных OpenF1 нет составов шин'
  if (reason.startsWith('No tyre model')) return 'Нет модели шин для этой трассы'
  return reason
}
