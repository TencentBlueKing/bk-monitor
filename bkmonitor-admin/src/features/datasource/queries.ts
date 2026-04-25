import { useMutation, useQuery } from '@tanstack/react-query';

import type { AdminEnvironment } from '../environments/schemas';
import {
  getDataIdComponentConfig,
  getDatasourceDetail,
  listDatasources,
  sampleKafkaData
} from './api';
import type { DataIdComponentConfigRequest, DataSourceListQuery } from './schemas';

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

export function useKafkaSample(environment: AdminEnvironment) {
  return useMutation({
    mutationFn: (params: { bkTenantId: string; bkDataId: number; size?: number }) =>
      sampleKafkaData(environment, params)
  });
}

export function useDataIdComponentConfig(
  environment: AdminEnvironment,
  query: DataIdComponentConfigRequest,
  enabled = false
) {
  return useQuery({
    queryKey: ['datasource', environment.id, environment, 'data-id-component-config', query],
    queryFn: () => getDataIdComponentConfig(environment, query),
    enabled,
    staleTime: 0
  });
}
