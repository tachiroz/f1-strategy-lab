/** Number formatting for the Russian UI: decimal comma, true minus sign, compact percentages. */

export const MINUS = '−'
const LOCALE = 'ru-RU'
const PERCENT = 100

const formatters = new Map<number, Intl.NumberFormat>()

function formatter(digits: number): Intl.NumberFormat {
  let cached = formatters.get(digits)
  if (!cached) {
    cached = new Intl.NumberFormat(LOCALE, {
      minimumFractionDigits: digits,
      maximumFractionDigits: digits,
    })
    formatters.set(digits, cached)
  }
  return cached
}

/** `4.348` → `4,35` (two digits by default). */
export function formatNumber(value: number, digits = 2): string {
  return formatter(digits).format(value).replace('-', MINUS)
}

/** Signed difference: `+1,02`, `−0,31`, `0,00`. */
export function formatSigned(value: number, digits = 2): string {
  const text = formatter(digits).format(Math.abs(value))
  if (Number(text.replace(',', '.').replace(/\s/g, '')) === 0) return text
  return `${value > 0 ? '+' : MINUS}${text}`
}

/** Share as a whole percentage; tiny non-zero shares read `<1%`, near-certain ones `>99%`. */
export function formatPercent(share: number): string {
  const percent = share * PERCENT
  if (percent > 0 && percent < 0.5) return '<1%'
  if (percent < PERCENT && percent > PERCENT - 0.5) return '>99%'
  return `${Math.round(percent)}%`
}

/** `[4,19; 4,51]` */
export function formatInterval(low: number, high: number, digits = 2, signed = false): string {
  const format = signed ? formatSigned : formatNumber
  return `[${format(low, digits)}; ${format(high, digits)}]`
}

/** Multiplier of the historical Safety Car rate: `×0,5`, `×1`. */
export function formatScale(scale: number): string {
  return `×${formatter(Number.isInteger(scale) ? 0 : 1).format(scale)}`
}

/** `2025-04-13` → `13 апреля 2025`. */
export function formatDate(isoDate: string): string {
  return new Intl.DateTimeFormat(LOCALE, {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
    timeZone: 'UTC',
  })
    .format(new Date(`${isoDate}T00:00:00Z`))
    .replace(/\s*г\.$/, '')
}

/** Russian plural: `pluralize(5, ['круг', 'круга', 'кругов'])` → `кругов`. */
export function pluralize(count: number, forms: readonly [string, string, string]): string {
  const mod10 = count % 10
  const mod100 = count % 100
  if (mod10 === 1 && mod100 !== 11) return forms[0]
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return forms[1]
  return forms[2]
}
