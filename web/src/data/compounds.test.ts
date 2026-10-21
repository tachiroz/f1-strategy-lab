import { describe, expect, it } from 'vitest'
import { COMPOUND_BY_ID, COMPOUNDS } from './compounds'

describe('COMPOUND_BY_ID', () => {
  it('indexes every compound by its id', () => {
    for (const compound of COMPOUNDS) {
      expect(COMPOUND_BY_ID[compound.id]).toBe(compound)
    }
    expect(Object.keys(COMPOUND_BY_ID)).toHaveLength(COMPOUNDS.length)
  })
})
