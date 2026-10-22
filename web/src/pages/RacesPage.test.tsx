import { fireEvent, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { mockApi, mockApiDown } from '../test/api'
import { renderAt } from '../test/render'

describe('RacesPage', () => {
  it('opens the showcase race with its scores against the grid', async () => {
    mockApi()
    renderAt('/races')
    expect(
      await screen.findByRole('heading', { level: 1, name: 'Bahrain Grand Prix' }),
    ).toBeVisible()
    expect(screen.getByText('прогноз вне выборки')).toBeInTheDocument()
    expect(await screen.findByText('2,42')).toBeInTheDocument()
    expect(screen.getByText(/к модели «финиш = решётка»/)).toHaveTextContent('0,30')
    expect(screen.getByText('Safety Car в гонке').nextElementSibling).toHaveTextContent('32%')
  })

  it('draws a row per driver and shows details on focus', async () => {
    mockApi()
    renderAt('/races?race=202504')
    const list = await screen.findByRole('list', { name: 'Пилоты' })
    const rows = within(list).getAllByRole('listitem')
    expect(rows).toHaveLength(20)
    fireEvent.focus(rows[0])
    const tooltip = screen.getByRole('tooltip')
    expect(tooltip).toHaveTextContent('Oscar Piastri · PIA')
    expect(tooltip).toHaveTextContent('P1')
  })

  it('switches the chart to its table twin', async () => {
    mockApi()
    renderAt('/races?race=202504')
    const figure = await screen.findByRole('figure', { name: 'Прогноз против факта' })
    fireEvent.click(within(figure).getByRole('button', { name: 'Таблица' }))
    const table = within(figure).getByRole('table', { name: 'Симулированные и реальные позиции' })
    expect(within(table).getAllByRole('row')).toHaveLength(21)
  })

  it('lists every driver with probabilities and a link to their strategies', async () => {
    mockApi()
    renderAt('/races?race=202504')
    const table = await screen.findByRole('table', { name: 'Исходы симуляции по пилотам' })
    expect(within(table).getByText('Oscar Piastri')).toBeInTheDocument()
    expect(
      within(table).getByRole('link', { name: 'Сравнить стратегии: Oscar Piastri' }),
    ).toHaveAttribute('href', '/strategy?race=202504&driver=piastri')
  })

  it('explains why a wet race is not simulated and does not ask for it', async () => {
    const fetchMock = mockApi()
    renderAt('/races?race=202501')
    expect(await screen.findByText('Эту гонку симулятор не считает')).toBeInTheDocument()
    expect(screen.getByText(/Мокрая гонка/)).toBeInTheDocument()
    expect(fetchMock.mock.calls.map(([url]) => String(url))).not.toContain(
      '/api/races/202501/simulation',
    )
  })

  it('says how to start the API when it is down', async () => {
    mockApiDown()
    renderAt('/races')
    expect(await screen.findByText('API не запущен')).toBeInTheDocument()
    expect(screen.getByText('uvicorn f1lab.api.main:app')).toBeInTheDocument()
  })
})
