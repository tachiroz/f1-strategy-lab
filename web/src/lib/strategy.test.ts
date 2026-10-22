import { describe, expect, it } from 'vitest'
import { describeSetupReason, parseStrategy } from './strategy'

describe('parseStrategy', () => {
  it('parses a one-stop and returns its stints', () => {
    expect(parseStrategy('m-25-h', 57)).toEqual({
      ok: true,
      notation: 'M-25-H',
      stints: [
        { compound: 'MEDIUM', first_lap: 1, last_lap: 25 },
        { compound: 'HARD', first_lap: 26, last_lap: 57 },
      ],
    })
  })

  it('keeps used starting tyres and drops a zero age, like the Python notation', () => {
    expect(parseStrategy('S3-14-M-32-M', 57)).toMatchObject({ ok: true, notation: 'S3-14-M-32-M' })
    expect(parseStrategy('S0-20-H', 57)).toMatchObject({ ok: true, notation: 'S-20-H' })
  })

  it.each([
    ['M25H', 'Формат'],
    ['X-20-H', 'Неизвестный состав: X'],
    ['S-57-H', 'с 1 по 56'],
    ['S-30-H-20-M', 'по возрастанию'],
    ['S-20-S', 'два разных состава'],
  ])('rejects %s', (text, message) => {
    const result = parseStrategy(text, 57)
    expect(result.ok).toBe(false)
    if (!result.ok) expect(result.error).toContain(message)
  })
})

describe('describeSetupReason', () => {
  it('explains the reasons the API gives in plain Russian', () => {
    expect(
      describeSetupReason("Australian Grand Prix: ['INTERMEDIATE'] tyres used; dry-only"),
    ).toContain('Мокрая гонка')
    expect(describeSetupReason("Qatar Grand Prix: ['UNKNOWN'] tyres used; dry-only")).toContain(
      'нет составов',
    )
    expect(describeSetupReason('No tyre model for interlagos')).toContain('Нет модели шин')
    expect(describeSetupReason('Something else')).toBe('Something else')
    expect(describeSetupReason(null)).toBe('')
  })
})
