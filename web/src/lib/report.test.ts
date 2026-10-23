import { describe, expect, it } from 'vitest'
import report from '../test/fixtures/report-202504.json'
import { headingId, markdownDataUrl, reportCommand, reportHeadings, withoutTitle } from './report'

describe('headingId', () => {
  it('keeps Cyrillic and joins words with hyphens', () => {
    expect(headingId('Взгляд симулятора')).toBe('report-взгляд-симулятора')
    expect(headingId(' Пит-стопы и шины ')).toBe('report-пит-стопы-и-шины')
  })
})

describe('reportHeadings', () => {
  it('lists the sections of a real report in order', () => {
    expect(reportHeadings(report.markdown).map((heading) => heading.text)).toEqual([
      'Итог',
      'Позиции',
      'Пит-стопы и шины',
      'Нейтрализации',
      'Взгляд симулятора',
    ])
  })
})

describe('withoutTitle', () => {
  it('drops the first-level title only', () => {
    const body = withoutTitle(report.markdown)
    expect(body.startsWith('> Автоматический отчёт')).toBe(true)
    expect(body).toContain('## Итог')
    expect(withoutTitle('## Итог\n')).toBe('## Итог\n')
  })
})

describe('markdownDataUrl', () => {
  it('encodes the text so that it decodes back unchanged', () => {
    const url = markdownDataUrl(report.markdown)
    const [prefix, data] = url.split(',', 2)
    expect(prefix).toBe('data:text/markdown;charset=utf-8')
    expect(decodeURIComponent(data)).toBe(report.markdown)
  })
})

describe('reportCommand', () => {
  it('names the season and round', () => {
    expect(reportCommand(2025, 4)).toBe('python -m f1lab.report --season 2025 --round 4')
  })
})
