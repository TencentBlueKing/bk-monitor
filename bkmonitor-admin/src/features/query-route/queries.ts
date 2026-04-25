import { useMutation, useQuery } from '@tanstack/react-query';

import type { AdminEnvironment } from '../environments/schemas';
import { queryRoutes, refreshQueryRoutes } from './api';
import type { QueryRouteQuery } from './schemas';

export function queryRouteQueryKey(environment: AdminEnvironment, query: QueryRouteQuery) {
  return ['query-route', environment.id, 'query', query] as const;
}

export function useQueryRoute(
  environment: AdminEnvironment,
  query: QueryRouteQuery,
  enabled = true
) {
  return useQuery({
    queryKey: queryRouteQueryKey(environment, query),
    queryFn: () => queryRoutes(environment, query),
    enabled,
    staleTime: Infinity,
    refetchOnWindowFocus: false,
    refetchOnMount: false
  });
}

export function useRefreshQueryRoute(environment: AdminEnvironment) {
  return useMutation({
    mutationFn: (query: QueryRouteQuery) => refreshQueryRoutes(environment, query)
  });
}
