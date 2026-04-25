import { useMutation, useQuery } from '@tanstack/react-query';

import type { AdminEnvironment } from '../environments/schemas';
import {
  getEsRuntimeOverview,
  getEsStorageDetail,
  listEsStorages,
  sampleEsStorage
} from './api';
import type { EsStorageListQuery } from './schemas';

export function useEsStorageList(
  environment: AdminEnvironment,
  query: EsStorageListQuery,
  enabled = true
) {
  return useQuery({
    queryKey: ['es-storage', environment.id, environment, 'list', query],
    queryFn: () => listEsStorages(environment, query),
    enabled
  });
}

export function useEsStorageDetail(
  environment: AdminEnvironment,
  bkTenantId: string,
  tableId: string
) {
  return useQuery({
    queryKey: ['es-storage', environment.id, environment, 'detail', bkTenantId, tableId],
    queryFn: () => getEsStorageDetail(environment, bkTenantId, tableId)
  });
}

export function useEsRuntimeOverview(environment: AdminEnvironment) {
  return useMutation({
    mutationFn: (params: { bkTenantId: string; tableId: string; index?: string }) =>
      getEsRuntimeOverview(environment, params)
  });
}

export function useEsStorageSample(environment: AdminEnvironment) {
  return useMutation({
    mutationFn: (params: { bkTenantId: string; tableId: string; index: string; timeField?: string }) =>
      sampleEsStorage(environment, params)
  });
}
