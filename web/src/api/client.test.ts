import { describe, expect, it, vi } from 'vitest'
import { mockApiDown } from '../test/api'
import { ApiError, getJson, queryString } from './client'

function respond(body: string, status: number) {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => new Response(body, { status })),
  )
}

describe('queryString', () => {
  it('repeats keys for arrays and skips empty input', () => {
    expect(queryString({ driver: 'piastri', strategy: ['M-25-H', 'S3-20-H'] })).toBe(
      '?driver=piastri&strategy=M-25-H&strategy=S3-20-H',
    )
    expect(queryString({ strategy: [] })).toBe('')
  })
})

describe('getJson', () => {
  it('returns the parsed body', async () => {
    respond('{"status":"ok"}', 200)
    await expect(getJson('/health')).resolves.toEqual({ status: 'ok' })
    expect(vi.mocked(fetch).mock.calls[0][0]).toBe('/api/health')
  })

  it('carries the API detail message and status', async () => {
    respond('{"detail":"No tyre model for interlagos"}', 422)
    const error = await getJson('/races/202421/simulation').catch((caught: unknown) => caught)
    expect(error).toBeInstanceOf(ApiError)
    expect(error).toMatchObject({ status: 422, message: 'No tyre model for interlagos' })
    expect((error as ApiError).unreachable).toBe(false)
  })

  it('treats a network failure as an unreachable API', async () => {
    mockApiDown()
    const error = await getJson('/races').catch((caught: unknown) => caught)
    expect((error as ApiError).unreachable).toBe(true)
  })

  it('treats a proxy error without JSON as an unreachable API', async () => {
    respond('', 502)
    const error = await getJson('/races').catch((caught: unknown) => caught)
    expect((error as ApiError).unreachable).toBe(true)
  })
})
