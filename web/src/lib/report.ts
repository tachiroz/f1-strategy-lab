/** Helpers for the Markdown race report served by the API. */

export interface ReportHeading {
  id: string
  text: string
}

const SECTION = /^## (.+)$/gm
const TITLE = /^# .*\n+/

/** Anchor of a report section: `Взгляд симулятора` → `report-взгляд-симулятора`. */
export function headingId(text: string): string {
  const slug = text
    .trim()
    .toLowerCase()
    .replace(/[^\p{L}\p{N}]+/gu, '-')
    .replace(/^-|-$/g, '')
  return `report-${slug}`
}

/** Second-level headings of the report, in order, for the table of contents. */
export function reportHeadings(markdown: string): ReportHeading[] {
  return [...markdown.matchAll(SECTION)].map(([, text]) => ({
    id: headingId(text),
    text: text.trim(),
  }))
}

/** The report without its first-level title: the page header already names the race. */
export function withoutTitle(markdown: string): string {
  return markdown.replace(TITLE, '')
}

/** `data:` URL of the report for a download link (UTF-8 Markdown). */
export function markdownDataUrl(markdown: string): string {
  return `data:text/markdown;charset=utf-8,${encodeURIComponent(markdown)}`
}

/** Command that writes the same report with its PNG charts. */
export function reportCommand(season: number, round: number): string {
  return `python -m f1lab.report --season ${season} --round ${round}`
}
