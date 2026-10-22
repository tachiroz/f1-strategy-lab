/** Thin fetch wrapper for the f1lab API (proxied to uvicorn by the Vite dev server). */

export const API_BASE = '/api'

/** Statuses a proxy answers with when the API process is not running. */
const UNREACHABLE_STATUSES = new Set([500, 502, 503, 504])

export class ApiError extends Error {
  /** HTTP status, or 0 when the API could not be reached at all. */
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }

  /** The API is not running (network error or a proxy error without a JSON body). */
  get unreachable(): boolean {
    return this.status === 0
  }
}

/** Query string with repeated keys for array values, e.g. `?strategy=A&strategy=B`. */
export function queryString(params: Record<string, string | readonly string[]>): string {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    for (const item of typeof value === 'string' ? [value] : value) search.append(key, item)
  }
  const text = search.toString()
  return text ? `?${text}` : ''
}

/** GET `API_BASE + path` and parse JSON; errors carry the API's `detail` message. */
export async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${API_BASE}${path}`, {
      signal,
      headers: { Accept: 'application/json' },
    })
  } catch (error) {
    if (signal?.aborted) throw error
    throw new ApiError(0, 'API недоступен')
  }
  const body: unknown = await response.json().catch(() => undefined)
  if (response.ok && body !== undefined) return body as T
  if (body === undefined && UNREACHABLE_STATUSES.has(response.status)) {
    throw new ApiError(0, 'API недоступен')
  }
  const detail =
    typeof body === 'object' && body !== null && 'detail' in body ? body.detail : undefined
  throw new ApiError(
    response.status,
    typeof detail === 'string' ? detail : `Ошибка API (${response.status})`,
  )
}
