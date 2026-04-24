import { useQuery } from '@tanstack/react-query';

import type { AdminEnvironment } from '../environments/schemas';
import { getDatasourceDetail, listDatasources } from './api';
import type { DataSourceListQuery } from './schemas';

export function useDatasourceList(environment: AdminEnvironment, query: DataSourceListQuery) {
  return useQuery({
    queryKey: ['datasource', environment.id, environment, 'list', query],
    queryFn: () => listDatasources(environment, query)
  });
}

export function useDatasourceDetail(
  environment: AdminEnvironment,
  bkTenantId: string,
  bkDataId: number
) {
  return useQuery({
    queryKey: ['datasource', environment.id, environment, 'detail', bkTenantId, bkDataId],
    queryFn: () => getDatasourceDetail(environment, bkTenantId, bkDataId)
  });
}
