import { useQuery } from '@tanstack/react-query';

import type { AdminEnvironment } from '../environments/schemas';
import { getBcsClusterDetail, listBcsClusters } from './api';
import type { BcsClusterListQuery } from './schemas';

export function useBcsClusterList(environment: AdminEnvironment, query: BcsClusterListQuery) {
  return useQuery({
    queryKey: ['bcs-cluster', environment.id, environment, 'list', query],
    queryFn: () => listBcsClusters(environment, query)
  });
}

export function useBcsClusterDetail(
  environment: AdminEnvironment,
  bkTenantId: string,
  clusterId: string
) {
  return useQuery({
    queryKey: ['bcs-cluster', environment.id, environment, 'detail', bkTenantId, clusterId],
    queryFn: () => getBcsClusterDetail(environment, bkTenantId, clusterId)
  });
}
