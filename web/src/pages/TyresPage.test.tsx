import { fireEvent, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { mockApi } from '../test/api'
import { renderAt } from '../test/render'

describe('TyresPage', () => {
  it('shows the degradation of every compound at the circuit', async () => {
    mockApi()
    renderAt('/tyres?circuit=bahrain')
    expect(
      await screen.findByRole('heading', { level: 1, name: 'Bahrain International Circuit' }),
    ).toBeVisible()
    expect(screen.getByText('Soft: деградация').nextElementSibling).toHaveTextContent('+0,126')
    expect(screen.getByText('Hard: деградация').nextElementSibling).toHaveTextContent('+0,113')
    expect(screen.getByText('Топливо и трасса').nextElementSibling).toHaveTextContent('−0,073')
  })

  it('reads the curve and the observed laps in the table view', async () => {
    mockApi()
    renderAt('/tyres?circuit=bahrain')
    const figure = await screen.findByRole('figure', { name: 'Время круга и возраст шины' })
    expect(within(figure).getByRole('img', { name: /Деградация шин/ })).toBeInTheDocument()
    fireEvent.click(within(figure).getByRole('button', { name: 'Таблица' }))
    const rows = within(within(figure).getByRole('table')).getAllByRole('row')
    expect(rows.length).toBeGreaterThan(40)
  })

  it('compares the circuits and highlights the selected one', async () => {
    mockApi()
    renderAt('/tyres?circuit=bahrain')
    const figure = await screen.findByRole('figure', { name: 'Деградация по трассам' })
    fireEvent.click(within(figure).getByRole('button', { name: 'Таблица' }))
    const table = within(figure).getByRole('table')
    expect(within(table).getAllByRole('row')).toHaveLength(25) // header + 24 circuits
    expect(within(table).getByText('Bahrain International Circuit')).toBeInTheDocument()
  })
})
