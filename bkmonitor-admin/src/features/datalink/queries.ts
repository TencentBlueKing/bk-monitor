import { useQuery } from '@tanstack/react-query';

import type { AdminEnvironment } from '../environments/schemas';
import {
  getClusterConfigComponentConfig,
  getClusterConfigDetail,
  getComponentConfig,
  getComponentDetail,
  getDataLinkComponentConfig,
  getDataLinkDetail,
  listClusterConfigs,
  listComponents,
  listDataLinks
} from './api';
import type {
  ClusterConfigListQuery,
  ComponentDetailParams,
  ComponentListQuery,
  DataLinkListQuery
} from './schemas';

export function useComponentList(environment: AdminEnvironment, query: ComponentListQuery) {
  return useQuery({
    queryKey: ['datalink', environment.id, environment, 'component-list', query],
    queryFn: () => listComponents(environment, query)
  });
}

export function useComponentDetail(
  environment: AdminEnvironment,
  params: ComponentDetailParams,
  enabled = true
) {
  return useQuery({
    queryKey: ['datalink', environment.id, environment, 'component-detail', params],
    queryFn: () => getComponentDetail(environment, params),
    enabled
  });
}

export function useComponentConfig(
  environment: AdminEnvironment,
  params: { bkTenantId: string; kind: string; namespace: string; name: string },
  enabled = false
) {
  return useQuery({
    queryKey: ['datalink', environment.id, environment, 'component-config', params],
    queryFn: () => getComponentConfig(environment, params),
    enabled,
    staleTime: 0
  });
}

export function useClusterConfigList(environment: AdminEnvironment, query: ClusterConfigListQuery) {
  return useQuery({
    queryKey: ['datalink', environment.id, environment, 'cluster-config-list', query],
    queryFn: () => listClusterConfigs(environment, query)
  });
}

export function useClusterConfigDetail(
  environment: AdminEnvironment,
  params: { bkTenantId: string; kind: string; namespace: string; name: string; include?: string[] },
  enabled = true
) {
  return useQuery({
    queryKey: ['datalink', environment.id, environment, 'cluster-config-detail', params],
    queryFn: () => getClusterConfigDetail(environment, params),
    enabled
  });
}

export function useClusterConfigComponentConfig(
  environment: AdminEnvironment,
  params: { bkTenantId: string; kind: string; namespace: string; name: string },
  enabled = false
) {
  return useQuery({
    queryKey: ['datalink', environment.id, environment, 'cluster-config-component-config', params],
    queryFn: () => getClusterConfigComponentConfig(environment, params),
    enabled,
    staleTime: 0
  });
}

export function useDataLinkList(environment: AdminEnvironment, query: DataLinkListQuery) {
  return useQuery({
    queryKey: ['datalink', environment.id, environment, 'datalink-list', query],
    queryFn: () => listDataLinks(environment, query)
  });
}

export function useDataLinkDetail(
  environment: AdminEnvironment,
  params: { bkTenantId: string; dataLinkName: string; include?: string[] },
  enabled = true
) {
  return useQuery({
    queryKey: ['datalink', environment.id, environment, 'datalink-detail', params],
    queryFn: () => getDataLinkDetail(environment, params),
    enabled
  });
}

export function useDataLinkComponentConfig(
  environment: AdminEnvironment,
  params: { bkTenantId: string; kind: string; namespace: string; name: string },
  enabled = false
) {
  return useQuery({
    queryKey: ['datalink', environment.id, environment, 'datalink-component-config', params],
    queryFn: () => getDataLinkComponentConfig(environment, params),
    enabled,
    staleTime: 0
  });
}
