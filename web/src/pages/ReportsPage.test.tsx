import { fireEvent, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { mockApi, mockApiDown, requestedUrls } from '../test/api'
import report202504 from '../test/fixtures/report-202504.json'
import { renderAt } from '../test/render'

async function openReport(path = '/reports') {
  renderAt(path)
  return screen.findByRole('article', { name: 'Отчёт' })
}

describe('ReportsPage', () => {
  afterEach(() => {
    // jsdom has no Clipboard API; a test may define one.
    Reflect.deleteProperty(navigator, 'clipboard')
  })

  it('renders the showcase report with the race in the page header', async () => {
    mockApi()
    const article = await openReport()
    expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1)
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Bahrain Grand Prix')
    expect(screen.getByText('со взглядом симулятора')).toBeInTheDocument()
    expect(within(article).getByRole('heading', { level: 2, name: 'Итог' })).toBeVisible()
    expect(within(article).getByText('Oscar Piastri', { selector: 'strong' })).toBeVisible()
    expect(within(article).getByText(/Отрыв от второго места — 15,5 с/)).toBeVisible()
  })

  it('renders the stops table and keeps the numbers right-aligned', async () => {
    mockApi()
    const article = await openReport('/reports?race=202504')
    const table = within(article).getByRole('table')
    expect(within(table).getAllByRole('row')).toHaveLength(21)
    expect(within(table).getByRole('columnheader', { name: 'Финиш' })).toHaveStyle({
      textAlign: 'right',
    })
    expect(within(table).getByText('Soft → Medium → Hard → Soft')).toBeInTheDocument()
  })

  it('links every section from the table of contents', async () => {
    mockApi()
    const article = await openReport()
    const toc = screen.getByRole('navigation', { name: 'Разделы отчёта' })
    const link = within(toc).getByRole('link', { name: 'Взгляд симулятора' })
    const heading = within(article).getByRole('heading', { name: 'Взгляд симулятора' })
    expect(link).toHaveAttribute('href', `#${heading.id}`)
    expect(
      await within(toc).findByRole('link', { name: 'График: прогноз против факта' }),
    ).toBeInTheDocument()
  })

  it('draws the forecast against the result for a simulated race', async () => {
    mockApi()
    renderAt('/reports?race=202504')
    expect(await screen.findByRole('figure', { name: 'Прогноз против факта' })).toBeVisible()
  })

  it('downloads the Markdown under the suggested file name', async () => {
    mockApi()
    await openReport()
    const download = screen.getByRole('link', { name: 'Скачать .md' })
    expect(download).toHaveAttribute('download', '2025-04-bahrain.md')
    const href = download.getAttribute('href') ?? ''
    expect(href.startsWith('data:text/markdown;charset=utf-8,')).toBe(true)
    expect(decodeURIComponent(href.split(',', 2)[1])).toBe(report202504.markdown)
  })

  it('copies the Markdown when the Clipboard API is available', async () => {
    mockApi()
    const writeText = vi.fn(async () => undefined)
    Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true })
    await openReport()
    fireEvent.click(screen.getByRole('button', { name: 'Копировать' }))
    expect(writeText).toHaveBeenCalledWith(report202504.markdown)
    expect(await screen.findByRole('button', { name: 'Скопировано' })).toBeInTheDocument()
  })

  it('hides the copy button without the Clipboard API', async () => {
    mockApi()
    await openReport()
    expect(screen.queryByRole('button', { name: 'Копировать' })).not.toBeInTheDocument()
  })

  it('opens the method links in a new tab', async () => {
    mockApi()
    const article = await openReport()
    expect(within(article).getByRole('link', { name: 'допущения симулятора' })).toHaveAttribute(
      'target',
      '_blank',
    )
  })

  it('reports a wet race without asking for a simulation', async () => {
    const fetchMock = mockApi()
    const article = await openReport('/reports?race=202501')
    expect(screen.getByText('без симуляции')).toBeInTheDocument()
    expect(within(article).getByText(/Симулятор эту гонку не считал/)).toBeVisible()
    expect(within(article).getByText(/Сейфти-кар проводил поле через пит-лейн/)).toBeVisible()
    expect(screen.queryByRole('figure')).not.toBeInTheDocument()
    expect(requestedUrls(fetchMock)).not.toContain('/api/races/202501/simulation')
  })

  it('says how to start the API when it is down', async () => {
    mockApiDown()
    renderAt('/reports')
    expect(await screen.findByText('API не запущен')).toBeInTheDocument()
  })
})
