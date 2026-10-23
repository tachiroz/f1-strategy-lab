import { screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { LAST_DONE_STAGE, STAGES } from './data/stages'
import { mockApi, mockApiDown } from './test/api'
import { renderAt } from './test/render'

describe('App', () => {
  it('renders the main heading', () => {
    mockApi()
    renderAt('/')
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Гоночная стратегия F1')
  })

  it('renders a roadmap card for every stage with finished ones and one next', () => {
    mockApi()
    renderAt('/')
    const roadmap = screen.getByRole('region', { name: 'От сырых данных до прогноза' })
    expect(within(roadmap).getAllByRole('listitem')).toHaveLength(STAGES.length)
    expect(within(roadmap).getAllByText('Готово')).toHaveLength(LAST_DONE_STAGE)
    expect(within(roadmap).queryAllByText('Следующий').length).toBeLessThanOrEqual(1)
  })

  it('shows the showcase driver simulated by the API in the hero', async () => {
    mockApi()
    renderAt('/')
    expect(await screen.findByText('72%')).toBeInTheDocument()
    expect(screen.getByText('Bahrain Grand Prix 2025')).toBeInTheDocument()
    expect(screen.getByText(/Oscar Piastri, реальная стратегия S3-14-M-32-M/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /сравнить стратегии/ })).toHaveAttribute(
      'href',
      '/strategy?race=202504&driver=piastri',
    )
  })

  it('shows no made-up metrics when the API is not running', async () => {
    mockApiDown()
    renderAt('/')
    expect(await screen.findByText(/Запустите API/)).toBeInTheDocument()
    for (const metric of ['Средняя позиция', 'P(подиум)', 'P(очки)']) {
      expect(screen.getByText(metric).nextElementSibling).toHaveTextContent('—')
    }
    expect(screen.getByText('иллюстрация')).toBeInTheDocument()
  })

  it('links the dashboard sections and keeps the selected race', async () => {
    mockApi()
    renderAt('/races?race=202504')
    const nav = screen.getByRole('navigation', { name: 'Разделы' })
    expect(within(nav).getByRole('link', { name: 'Стратегии' })).toHaveAttribute(
      'href',
      '/strategy?race=202504',
    )
    expect(within(nav).getByRole('link', { name: 'Гонки' })).toHaveAttribute('aria-current', 'page')
    expect(within(nav).getByRole('link', { name: 'Отчёты' })).toHaveAttribute(
      'href',
      '/reports?race=202504',
    )
  })

  it('answers unknown paths with a 404 page', () => {
    mockApi()
    renderAt('/nowhere')
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Такой страницы нет')
  })
})
