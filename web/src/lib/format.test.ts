import { describe, expect, it } from 'vitest'
import {
  formatDate,
  formatInterval,
  formatNumber,
  formatPercent,
  formatScale,
  formatSigned,
  MINUS,
  pluralize,
} from './format'

describe('formatNumber', () => {
  it('uses a decimal comma and a true minus sign', () => {
    expect(formatNumber(4.3482)).toBe('4,35')
    expect(formatNumber(-0.305, 1)).toBe(`${MINUS}0,3`)
    expect(formatNumber(5000, 0)).toMatch(/^5\s000$/)
  })
})

describe('formatSigned', () => {
  it('always shows the sign of a non-zero difference', () => {
    expect(formatSigned(1.02)).toBe('+1,02')
    expect(formatSigned(-0.305)).toBe(`${MINUS}0,31`)
  })

  it('leaves zero (also after rounding) unsigned', () => {
    expect(formatSigned(0)).toBe('0,00')
    expect(formatSigned(-0.001)).toBe('0,00')
  })
})

describe('formatPercent', () => {
  it('rounds to whole percent and flags tiny and near-certain shares', () => {
    expect(formatPercent(0.7176)).toBe('72%')
    expect(formatPercent(0)).toBe('0%')
    expect(formatPercent(0.0004)).toBe('<1%')
    expect(formatPercent(0.9996)).toBe('>99%')
    expect(formatPercent(1)).toBe('100%')
  })
})

describe('formatInterval', () => {
  it('formats both ends, optionally signed', () => {
    expect(formatInterval(4.188, 4.508)).toBe('[4,19; 4,51]')
    expect(formatInterval(-0.35, -0.26, 2, true)).toBe(`[${MINUS}0,35; ${MINUS}0,26]`)
  })
})

describe('formatScale', () => {
  it('shows halves with one digit and whole multipliers without', () => {
    expect(formatScale(0.5)).toBe('×0,5')
    expect(formatScale(2)).toBe('×2')
  })
})

describe('formatDate', () => {
  it('writes the date in words without the year suffix', () => {
    expect(formatDate('2025-04-13')).toBe('13 апреля 2025')
  })
})

describe('pluralize', () => {
  it.each([
    [1, 'круг'],
    [3, 'круга'],
    [5, 'кругов'],
    [11, 'кругов'],
    [21, 'круг'],
    [57, 'кругов'],
  ])('%i → %s', (count, form) => {
    expect(pluralize(count, ['круг', 'круга', 'кругов'])).toBe(form)
  })
})
