import { useQuery } from '@tanstack/react-query';

import type { AdminEnvironment } from '../environments/schemas';
import { getClusterInfoDetail, getComponentConfig, listClusterInfos } from './api';
import type { ClusterInfoListQuery, ComponentConfigRequest } from './schemas';

export function useClusterInfoList(
  environment: AdminEnvironment,
  query: ClusterInfoListQuery,
  enabled = true
) {
  return useQuery({
    queryKey: ['cluster-info', environment.id, environment, 'list', query],
    queryFn: () => listClusterInfos(environment, query),
    enabled
  });
}

export function useClusterInfoDetail(
  environment: AdminEnvironment,
  bkTenantId: string,
  clusterId: number
) {
  return useQuery({
    queryKey: ['cluster-info', environment.id, environment, 'detail', bkTenantId, clusterId],
    queryFn: () => getClusterInfoDetail(environment, bkTenantId, clusterId)
  });
}

export function componentConfigQueryKey(
  environment: AdminEnvironment,
  query: ComponentConfigRequest
) {
  return ['cluster-info', environment.id, 'component-config', query] as const;
}

export function useComponentConfig(
  environment: AdminEnvironment,
  query: ComponentConfigRequest,
  enabled = false
) {
  return useQuery({
    queryKey: componentConfigQueryKey(environment, query),
    queryFn: () => getComponentConfig(environment, query),
    enabled,
    staleTime: 0
  });
}
