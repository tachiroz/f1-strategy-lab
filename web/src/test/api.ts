/**
 * Fake API for component tests, serving real responses recorded by
 * tests/fixtures/export_web_fixtures.py (and validated against the API models by pytest).
 */
import { vi } from 'vitest'
import circuits from './fixtures/circuits.json'
import race202501 from './fixtures/race-202501.json'
import race202504 from './fixtures/race-202504.json'
import races from './fixtures/races.json'
import report202501 from './fixtures/report-202501.json'
import report202504 from './fixtures/report-202504.json'
import scSensitivity from './fixtures/sc-sensitivity-202504.json'
import simulation from './fixtures/simulation-202504.json'
import strategies from './fixtures/strategies-202504.json'
import tyres from './fixtures/tyres-bahrain.json'

/** The strategies the comparison fixtures were recorded with. */
export const RECORDED_STRATEGIES = 'driver=piastri&strategy=M-25-H&strategy=S3-20-H'

export const FIXTURES: Readonly<Record<string, unknown>> = {
  '/api/races': races,
  '/api/races/202504': race202504,
  '/api/races/202501': race202501,
  '/api/races/202504/simulation': simulation,
  '/api/races/202504/report': report202504,
  '/api/races/202501/report': report202501,
  [`/api/races/202504/strategies?${RECORDED_STRATEGIES}`]: strategies,
  [`/api/races/202504/sc-sensitivity?${RECORDED_STRATEGIES}`]: scSensitivity,
  '/api/circuits': circuits,
  '/api/circuits/bahrain/tyres': tyres,
}

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

/** Serve the fixtures; unknown URLs answer 404 like the API does. Returns the fetch mock. */
export function mockApi(routes: Readonly<Record<string, unknown>> = FIXTURES) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const url = new URL(String(input), 'http://localhost')
    const body = routes[`${url.pathname}${url.search}`]
    return body === undefined ? json({ detail: `No fixture for ${url}` }, 404) : json(body)
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

/** The API process is not running: every request fails at the network level. */
export function mockApiDown() {
  const fetchMock = vi.fn(async () => {
    throw new TypeError('Failed to fetch')
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

/** Paths and query strings the app has requested so far. */
export function requestedUrls(fetchMock: ReturnType<typeof vi.fn>): string[] {
  return fetchMock.mock.calls.map(([input]) => {
    const url = new URL(String(input), 'http://localhost')
    return decodeURIComponent(`${url.pathname}${url.search}`)
  })
}
