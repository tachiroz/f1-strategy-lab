import { describe, expect, it } from 'vitest'
import { LAST_DONE_STAGE, STAGES, stageStatus } from './stages'

describe('stageStatus', () => {
  it('marks finished stages done, the following one next and the rest planned', () => {
    expect(stageStatus(1, 2)).toBe('done')
    expect(stageStatus(2, 2)).toBe('done')
    expect(stageStatus(3, 2)).toBe('next')
    expect(stageStatus(4, 2)).toBe('planned')
  })

  it('makes the first stage next when nothing is done yet', () => {
    expect(stageStatus(1, 0)).toBe('next')
  })
})

describe('STAGES', () => {
  it('has sequential ids starting at 1', () => {
    expect(STAGES.map((stage) => stage.id)).toEqual(STAGES.map((_, index) => index + 1))
  })

  it('keeps LAST_DONE_STAGE inside the roadmap', () => {
    expect(LAST_DONE_STAGE).toBeGreaterThanOrEqual(0)
    expect(LAST_DONE_STAGE).toBeLessThanOrEqual(STAGES.length)
  })
})
