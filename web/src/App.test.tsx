import { render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import App from './App.tsx'
import { LAST_DONE_STAGE, STAGES } from './data/stages'

describe('App', () => {
  it('renders the main heading', () => {
    render(<App />)
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Гоночная стратегия F1')
  })

  it('renders a roadmap card for every stage with finished ones and one next', () => {
    render(<App />)
    const roadmap = screen.getByRole('region', { name: 'От сырых данных до прогноза' })
    expect(within(roadmap).getAllByRole('listitem')).toHaveLength(STAGES.length)
    expect(within(roadmap).getAllByText('Готово')).toHaveLength(LAST_DONE_STAGE)
    expect(within(roadmap).getAllByText('Следующий')).toHaveLength(1)
  })

  it('does not show simulator numbers before the simulator exists', () => {
    render(<App />)
    for (const metric of ['Средняя позиция', 'P(подиум)', 'P(очки)']) {
      expect(screen.getByText(metric).nextElementSibling).toHaveTextContent('—')
    }
  })
})
