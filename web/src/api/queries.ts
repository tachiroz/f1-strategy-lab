import { keepPreviousData, QueryClient, useQuery } from '@tanstack/react-query'
import { ApiError, getJson, queryString } from './client'
import type {
  CircuitSummary,
  RaceDetail,
  RaceReport,
  RaceSimulation,
  RaceSummary,
  ScSensitivity,
  StrategyComparison,
  TyreModel,
} from './types'

/** The database does not change while the API runs and the seed is fixed: never refetch. */
export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: Infinity,
        refetchOnWindowFocus: false,
        // Client errors (bad strategy, unknown race) will not fix themselves.
        retry: (failures, error) =>
          failures < 1 && !(error instanceof ApiError && error.status >= 400),
      },
    },
  })
}

export function useRaces() {
  return useQuery({
    queryKey: ['races'],
    queryFn: ({ signal }) => getJson<RaceSummary[]>('/races', signal),
  })
}

export function useRace(raceId: number | undefined) {
  return useQuery({
    queryKey: ['race', raceId],
    queryFn: ({ signal }) => getJson<RaceDetail>(`/races/${raceId}`, signal),
    enabled: raceId !== undefined,
  })
}

export function useSimulation(raceId: number | undefined, enabled = true) {
  return useQuery({
    queryKey: ['simulation', raceId],
    queryFn: ({ signal }) => getJson<RaceSimulation>(`/races/${raceId}/simulation`, signal),
    enabled: raceId !== undefined && enabled,
  })
}

export function useReport(raceId: number | undefined) {
  return useQuery({
    queryKey: ['report', raceId],
    queryFn: ({ signal }) => getJson<RaceReport>(`/races/${raceId}/report`, signal),
    enabled: raceId !== undefined,
  })
}

interface StrategyRequest {
  raceId: number | undefined
  driverId: string | undefined
  strategies: readonly string[]
}

function strategyPath(endpoint: string, { raceId, driverId, strategies }: StrategyRequest) {
  return `/races/${raceId}/${endpoint}${queryString({ driver: driverId ?? '', strategy: strategies })}`
}

/** Comparison of a driver's strategies; the previous result stays on screen while recomputing. */
export function useStrategyComparison(request: StrategyRequest) {
  return useQuery({
    queryKey: ['strategies', request.raceId, request.driverId, request.strategies],
    queryFn: ({ signal }) =>
      getJson<StrategyComparison>(strategyPath('strategies', request), signal),
    enabled: request.raceId !== undefined && request.driverId !== undefined,
    placeholderData: keepPreviousData,
  })
}

export function useScSensitivity(request: StrategyRequest) {
  return useQuery({
    queryKey: ['sc-sensitivity', request.raceId, request.driverId, request.strategies],
    queryFn: ({ signal }) =>
      getJson<ScSensitivity>(strategyPath('sc-sensitivity', request), signal),
    enabled: request.raceId !== undefined && request.driverId !== undefined,
    placeholderData: keepPreviousData,
  })
}

export function useCircuits() {
  return useQuery({
    queryKey: ['circuits'],
    queryFn: ({ signal }) => getJson<CircuitSummary[]>('/circuits', signal),
  })
}

export function useTyres(circuitId: string | undefined) {
  return useQuery({
    queryKey: ['tyres', circuitId],
    queryFn: ({ signal }) => getJson<TyreModel>(`/circuits/${circuitId}/tyres`, signal),
    enabled: circuitId !== undefined,
    placeholderData: keepPreviousData,
  })
}
