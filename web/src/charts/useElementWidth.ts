import { useLayoutEffect, useRef, useState } from 'react'

/** Width used before the first measurement and where ResizeObserver is missing (tests). */
export const FALLBACK_WIDTH = 720

/** Track the content width of an element so SVG charts can lay out in real pixels. */
export function useElementWidth<T extends HTMLElement>() {
  const ref = useRef<T>(null)
  const [width, setWidth] = useState(FALLBACK_WIDTH)

  useLayoutEffect(() => {
    const element = ref.current
    if (!element) return
    // Measure before the first paint: drawing at the fallback width would overflow a phone
    // screen for a frame, and mobile browsers zoom the page out to fit it.
    if (element.clientWidth > 0) setWidth(element.clientWidth)
    if (typeof ResizeObserver === 'undefined') return
    const observer = new ResizeObserver(([entry]) => {
      if (entry.contentRect.width > 0) setWidth(Math.round(entry.contentRect.width))
    })
    observer.observe(element)
    return () => observer.disconnect()
  }, [])

  return [ref, width] as const
}
