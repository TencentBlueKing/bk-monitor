import { useQuery } from '@tanstack/react-query';

import type { AdminEnvironment } from '../environments/schemas';
import { getApmApplicationDetail, listApmApplications, listApmServices } from './api';
import type { ApmApplicationListQuery, ApmServiceListQuery } from './schemas';

export function useApmApplicationList(
  environment: AdminEnvironment,
  query: ApmApplicationListQuery
) {
  return useQuery({
    queryKey: ['apm', environment.id, environment, 'application-list', query],
    queryFn: () => listApmApplications(environment, query)
  });
}

export function useApmApplicationDetail(
  environment: AdminEnvironment,
  params: { bkTenantId: string; applicationId: number },
  enabled = true
) {
  return useQuery({
    queryKey: ['apm', environment.id, environment, 'application-detail', params],
    queryFn: () =>
      getApmApplicationDetail(environment, {
        ...params,
        include: ['datasources', 'result_tables', 'custom_reports', 'summary']
      }),
    enabled
  });
}

export function useApmServiceList(
  environment: AdminEnvironment,
  query: ApmServiceListQuery,
  enabled = true
) {
  return useQuery({
    queryKey: ['apm', environment.id, environment, 'service-list', query],
    queryFn: () => listApmServices(environment, query),
    enabled
  });
}
