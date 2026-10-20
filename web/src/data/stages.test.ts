import { describe, expect, it } from 'vitest'
import { CURRENT_STAGE, STAGES, stageStatus } from './stages'

describe('stageStatus', () => {
  it('marks earlier stages done, the current one active and later ones planned', () => {
    expect(stageStatus(1, 2)).toBe('done')
    expect(stageStatus(2, 2)).toBe('active')
    expect(stageStatus(3, 2)).toBe('planned')
  })
})

describe('STAGES', () => {
  it('has sequential ids starting at 1', () => {
    expect(STAGES.map((stage) => stage.id)).toEqual(STAGES.map((_, index) => index + 1))
  })

  it('contains the current stage', () => {
    expect(STAGES.some((stage) => stage.id === CURRENT_STAGE)).toBe(true)
  })
})
