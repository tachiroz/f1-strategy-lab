import { fireEvent, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { mockApi, RECORDED_STRATEGIES, requestedUrls } from '../test/api'
import { renderAt } from '../test/render'

const RECORDED = `/strategy?race=202504&${RECORDED_STRATEGIES.replaceAll('strategy=', 's=')}`

describe('StrategyPage', () => {
  it('compares the actual strategy with the alternatives', async () => {
    mockApi()
    renderAt(RECORDED)
    expect(
      await screen.findByRole('heading', {
        level: 1,
        name: 'Oscar Piastri: какая стратегия лучше',
      }),
    ).toBeVisible()
    expect(await screen.findByText('4,35')).toBeInTheDocument()
    expect(screen.getByText('4,04')).toBeInTheDocument()
    expect(screen.getByText('5,37')).toBeInTheDocument()
    expect(screen.getByText(/лучше фактической/)).toHaveTextContent('0,31')
    expect(screen.getByText(/хуже фактической/)).toHaveTextContent('+1,02')
  })

  it('draws the finishing distribution and the Safety Car sensitivity', async () => {
    mockApi()
    renderAt(RECORDED)
    expect(
      await screen.findByRole('figure', { name: 'Распределение финишной позиции' }),
    ).toBeVisible()
    const sensitivity = await screen.findByRole('figure', { name: 'Чувствительность к Safety Car' })
    fireEvent.click(within(sensitivity).getByRole('button', { name: 'Таблица' }))
    const table = within(sensitivity).getByRole('table')
    expect(within(table).getAllByRole('row')).toHaveLength(6) // header + 5 Safety Car scales
    expect(within(table).getByText('×1')).toBeInTheDocument()
  })

  it('hides the form when two alternatives are already compared', async () => {
    mockApi()
    renderAt(RECORDED)
    await screen.findByText('Стратегии для сравнения')
    expect(screen.queryByLabelText('Добавить стратегию')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Убрать стратегию S3-20-H' })).toBeInTheDocument()
  })

  it('checks the notation before asking the API and adds valid strategies', async () => {
    const fetchMock = mockApi()
    renderAt('/strategy?race=202504&driver=piastri&s=M-25-H')
    const input = await screen.findByLabelText('Добавить стратегию')
    const add = screen.getByRole('button', { name: 'Добавить' })

    fireEvent.change(input, { target: { value: 'S-60-H' } })
    expect(screen.getByText('Пит-стоп возможен на кругах с 1 по 56')).toBeInTheDocument()
    expect(add).toBeDisabled()

    fireEvent.change(input, { target: { value: 'm-25-h' } })
    expect(screen.getByText('Такая стратегия уже есть в сравнении')).toBeInTheDocument()

    fireEvent.change(input, { target: { value: 's3-20-h' } })
    expect(add).toBeEnabled()
    fireEvent.click(add)
    await screen.findByText('5,37')
    expect(requestedUrls(fetchMock)).toContain(
      '/api/races/202504/strategies?driver=piastri&strategy=M-25-H&strategy=S3-20-H',
    )
  })

  it('offers the strategies the field actually ran', async () => {
    const fetchMock = mockApi()
    renderAt('/strategy?race=202504&driver=piastri')
    const chip = await screen.findByRole('button', { name: 'M-17-M-32-H' })
    expect(screen.queryByRole('button', { name: 'S3-14-M-32-M' })).not.toBeInTheDocument()
    fireEvent.click(chip)
    await screen.findByRole('button', { name: 'Убрать стратегию M-17-M-32-H' })
    expect(requestedUrls(fetchMock)).toContain(
      '/api/races/202504/strategies?driver=piastri&strategy=M-17-M-32-H',
    )
  })
})
