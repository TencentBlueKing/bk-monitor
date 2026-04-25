import { useQuery } from '@tanstack/react-query';

import type { AdminEnvironment } from '../environments/schemas';
import { getClusterInfoDetail, listClusterInfos } from './api';
import type { ClusterInfoListQuery } from './schemas';

export function useClusterInfoList(environment: AdminEnvironment, query: ClusterInfoListQuery) {
  return useQuery({
    queryKey: ['cluster-info', environment.id, environment, 'list', query],
    queryFn: () => listClusterInfos(environment, query)
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
