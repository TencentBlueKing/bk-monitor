import { useQuery } from '@tanstack/react-query';

import type { AdminEnvironment } from '../environments/schemas';
import { getResultTableDetail, listResultTableFields, listResultTables } from './api';
import type { ResultTableFieldListQuery, ResultTableListQuery } from './schemas';

export function useResultTableList(environment: AdminEnvironment, query: ResultTableListQuery) {
  return useQuery({
    queryKey: ['result-table', environment.id, environment, 'list', query],
    queryFn: () => listResultTables(environment, query)
  });
}

export function useResultTableDetail(
  environment: AdminEnvironment,
  bkTenantId: string,
  tableId: string
) {
  return useQuery({
    queryKey: ['result-table', environment.id, environment, 'detail', bkTenantId, tableId],
    queryFn: () => getResultTableDetail(environment, bkTenantId, tableId)
  });
}

export function useResultTableFields(
  environment: AdminEnvironment,
  query: ResultTableFieldListQuery
) {
  return useQuery({
    queryKey: ['result-table', environment.id, environment, 'fields', query],
    queryFn: () => listResultTableFields(environment, query)
  });
}
