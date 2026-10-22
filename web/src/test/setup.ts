import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach, vi } from 'vitest'

// jsdom does not implement scrolling; the app scrolls to the top on navigation.
window.scrollTo = vi.fn() as typeof window.scrollTo

// Vitest runs without globals, so Testing Library cannot register cleanup by itself.
afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})
