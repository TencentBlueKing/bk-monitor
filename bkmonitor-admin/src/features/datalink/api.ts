import type { AdminEnvironment } from '../environments/schemas';
import { kernelRpcClient } from '../kernel-rpc/client';
import {
  componentListResponseSchema,
  componentDetailResponseSchema,
  componentConfigResponseSchema,
  clusterConfigListResponseSchema,
  clusterConfigDetailResponseSchema,
  datalinkListResponseSchema,
  datalinkDetailResponseSchema,
  type ComponentListQuery,
  type ComponentListResponse,
  type ComponentDetailParams,
  type ComponentDetailResponse,
  type ClusterConfigListQuery,
  type ClusterConfigListResponse,
  type ClusterConfigDetailResponse,
  type DataLinkListQuery,
  type DataLinkListResponse,
  type DataLinkDetailResponse,
  type ComponentConfigResponse
} from './schemas';
import { compactObject } from '../../shared/utils/format';
import { toBackendPagination } from '../../shared/schemas/pagination';

export async function listComponents(
  environment: AdminEnvironment,
  query: ComponentListQuery
): Promise<ComponentListResponse> {
  const envelope = await kernelRpcClient.call<unknown>({
    environment,
    operation: 'datalink.component_list',
    params: compactObject({
      bk_tenant_id: query.bkTenantId,
      kind: query.kind,
      namespace: query.namespace,
      search: query.search,
      status: query.status,
      bk_data_id: query.bkDataId,
      data_type: query.dataType,
      vm_cluster_name: query.vmClusterName,
      es_cluster_name: query.esClusterName,
      doris_cluster_name: query.dorisClusterName,
      has_data_link: query.hasDataLink,
      ...toBackendPagination(query)
    })
  });

  return componentListResponseSchema.parse(envelope.data);
}

export async function getComponentDetail(
  environment: AdminEnvironment,
  params: ComponentDetailParams
): Promise<ComponentDetailResponse> {
  const envelope = await kernelRpcClient.call<unknown>({
    environment,
    operation: 'datalink.component_detail',
    params: compactObject({
      bk_tenant_id: params.bkTenantId,
      kind: params.kind,
      namespace: params.namespace,
      name: params.name,
      include: params.include
    })
  });

  return componentDetailResponseSchema.parse(envelope.data);
}

export async function getComponentConfig(
  environment: AdminEnvironment,
  params: { bkTenantId: string; kind: string; namespace: string; name: string }
): Promise<ComponentConfigResponse> {
  const envelope = await kernelRpcClient.call<unknown>({
    environment,
    operation: 'datalink.component_config',
    params: compactObject({
      bk_tenant_id: params.bkTenantId,
      kind: params.kind,
      namespace: params.namespace,
      name: params.name
    })
  });

  return componentConfigResponseSchema.parse(envelope.data);
}

export async function listClusterConfigs(
  environment: AdminEnvironment,
  query: ClusterConfigListQuery
): Promise<ClusterConfigListResponse> {
  const envelope = await kernelRpcClient.call<unknown>({
    environment,
    operation: 'datalink.cluster_config_list',
    params: compactObject({
      bk_tenant_id: query.bkTenantId,
      kind: query.kind,
      namespace: query.namespace,
      search: query.search,
      ...toBackendPagination(query)
    })
  });

  return clusterConfigListResponseSchema.parse(envelope.data);
}

export async function getClusterConfigDetail(
  environment: AdminEnvironment,
  params: { bkTenantId: string; kind: string; namespace: string; name: string; include?: string[] }
): Promise<ClusterConfigDetailResponse> {
  const envelope = await kernelRpcClient.call<unknown>({
    environment,
    operation: 'datalink.cluster_config_detail',
    params: compactObject({
      bk_tenant_id: params.bkTenantId,
      kind: params.kind,
      namespace: params.namespace,
      name: params.name,
      include: params.include
    })
  });

  return clusterConfigDetailResponseSchema.parse(envelope.data);
}

export async function getClusterConfigComponentConfig(
  environment: AdminEnvironment,
  params: { bkTenantId: string; kind: string; namespace: string; name: string }
): Promise<ComponentConfigResponse> {
  const envelope = await kernelRpcClient.call<unknown>({
    environment,
    operation: 'datalink.cluster_config_component_config',
    params: compactObject({
      bk_tenant_id: params.bkTenantId,
      kind: params.kind,
      namespace: params.namespace,
      name: params.name
    })
  });

  return componentConfigResponseSchema.parse(envelope.data);
}

export async function listDataLinks(
  environment: AdminEnvironment,
  query: DataLinkListQuery
): Promise<DataLinkListResponse> {
  const envelope = await kernelRpcClient.call<unknown>({
    environment,
    operation: 'datalink.datalink_list',
    params: compactObject({
      bk_tenant_id: query.bkTenantId,
      namespace: query.namespace,
      search: query.search,
      data_link_strategy: query.dataLinkStrategy,
      bk_data_id: query.bkDataId,
      ...toBackendPagination(query)
    })
  });

  return datalinkListResponseSchema.parse(envelope.data);
}

export async function getDataLinkDetail(
  environment: AdminEnvironment,
  params: { bkTenantId: string; dataLinkName: string; include?: string[] }
): Promise<DataLinkDetailResponse> {
  const envelope = await kernelRpcClient.call<unknown>({
    environment,
    operation: 'datalink.datalink_detail',
    params: compactObject({
      bk_tenant_id: params.bkTenantId,
      data_link_name: params.dataLinkName,
      include: params.include
    })
  });

  return datalinkDetailResponseSchema.parse(envelope.data);
}

export async function getDataLinkComponentConfig(
  environment: AdminEnvironment,
  params: { bkTenantId: string; kind: string; namespace: string; name: string }
): Promise<ComponentConfigResponse> {
  const envelope = await kernelRpcClient.call<unknown>({
    environment,
    operation: 'datalink.datalink_component_config',
    params: compactObject({
      bk_tenant_id: params.bkTenantId,
      kind: params.kind,
      namespace: params.namespace,
      name: params.name
    })
  });

  return componentConfigResponseSchema.parse(envelope.data);
}
