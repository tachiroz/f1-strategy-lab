import { describe, expect, it } from 'vitest'
import { BAR_RADIUS, columnPath, dodgeLabels, localPoint } from './geometry'

describe('columnPath', () => {
  it('rounds the top corners and keeps the baseline square', () => {
    const path = columnPath(10, 20, 12, 50)
    expect(path.startsWith('M10,70')).toBe(true)
    expect(path).toContain(`V${20 + BAR_RADIUS}`)
    expect(path).toContain('V70Z')
  })

  it('never uses a radius larger than half the width or the height', () => {
    expect(columnPath(0, 0, 4, 1)).toContain('V1')
  })
})

describe('dodgeLabels', () => {
  it('spreads colliding labels and keeps their order', () => {
    const placed = dodgeLabels(
      [
        { id: 'a', y: 50 },
        { id: 'b', y: 52 },
        { id: 'c', y: 100 },
      ],
      14,
      0,
      200,
    )
    expect(placed.get('a')).toBe(50)
    expect(placed.get('b')).toBe(64)
    expect(placed.get('c')).toBe(100)
  })

  it('pushes labels back inside the bottom edge', () => {
    const placed = dodgeLabels(
      [
        { id: 'a', y: 195 },
        { id: 'b', y: 198 },
      ],
      14,
      0,
      200,
    )
    expect(placed.get('b')).toBe(200)
    expect(placed.get('a')).toBe(186)
  })
})

describe('localPoint', () => {
  it('measures from the element corner', () => {
    const element = document.createElement('div')
    element.getBoundingClientRect = () => ({ left: 10, top: 20 }) as DOMRect
    expect(localPoint({ clientX: 15, clientY: 50 }, element)).toEqual({ x: 5, y: 30 })
  })
})
