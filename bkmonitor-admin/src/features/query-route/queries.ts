import { useMutation, useQuery } from '@tanstack/react-query';

import type { AdminEnvironment } from '../environments/schemas';
import { queryRoutes, refreshQueryRoutes } from './api';
import type { QueryRouteQuery } from './schemas';

export function useQueryRoute(environment: AdminEnvironment, query: QueryRouteQuery, enabled = true) {
  return useQuery({
    queryKey: ['query-route', environment.id, environment, 'query', query],
    queryFn: () => queryRoutes(environment, query),
    enabled
  });
}

export function useRefreshQueryRoute(environment: AdminEnvironment) {
  return useMutation({
    mutationFn: (query: QueryRouteQuery) => refreshQueryRoutes(environment, query)
  });
}
