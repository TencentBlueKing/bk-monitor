import type { AdminEnvironment } from '../environments/schemas';
import { kernelRpcClient } from '../kernel-rpc/client';
import { toBackendPagination } from '../../shared/schemas/pagination';
import { compactObject } from '../../shared/utils/format';
import {
  clusterInfoDetailResponseSchema,
  clusterInfoListResponseSchema,
  componentConfigResponseSchema,
  type ClusterInfoDetailResponse,
  type ClusterInfoListQuery,
  type ClusterInfoListResponse,
  type ComponentConfigRequest,
  type ComponentConfigResponse
} from './schemas';

export async function listClusterInfos(
  environment: AdminEnvironment,
  query: ClusterInfoListQuery
): Promise<ClusterInfoListResponse> {
  const envelope = await kernelRpcClient.call<unknown>({
    environment,
    operation: 'cluster_info.list',
    params: compactObject({
      bk_tenant_id: query.bkTenantId,
      cluster_name: query.clusterName,
      cluster_type: query.clusterType,
      is_default_cluster: query.isDefaultCluster,
      registered_system: query.registeredSystem,
      include: query.include,
      ...toBackendPagination(query)
    })
  });

  return clusterInfoListResponseSchema.parse(envelope.data);
}

export async function getClusterInfoDetail(
  environment: AdminEnvironment,
  bkTenantId: string,
  clusterId: number,
  include?: string[]
): Promise<ClusterInfoDetailResponse> {
  const envelope = await kernelRpcClient.call<unknown>({
    environment,
    operation: 'cluster_info.detail',
    params: compactObject({
      bk_tenant_id: bkTenantId,
      cluster_id: clusterId,
      include
    })
  });

  return clusterInfoDetailResponseSchema.parse(normalizeClusterInfoDetailPayload(envelope.data));
}

function normalizeClusterInfoDetailPayload(payload: unknown) {
  if (!payload || typeof payload !== 'object') {
    return payload;
  }

  const record = payload as Record<string, unknown>;
  return {
    ...record,
    cluster_info: record.cluster_info ?? record.cluster,
    cluster_configs: Array.isArray(record.cluster_configs)
      ? record.cluster_configs.map((item) => normalizeClusterConfig(item))
      : []
  };
}

export async function getComponentConfig(
  environment: AdminEnvironment,
  query: ComponentConfigRequest
): Promise<ComponentConfigResponse> {
  const envelope = await kernelRpcClient.call<unknown>({
    environment,
    operation: 'cluster_info.component_config',
    params: compactObject({
      bk_tenant_id: query.bkTenantId,
      cluster_id: query.clusterId,
      namespace: query.namespace,
      kind: query.kind,
      name: query.name
    })
  });

  return componentConfigResponseSchema.parse(envelope.data);
}

function normalizeClusterConfig(config: unknown) {
  if (!config || typeof config !== 'object') {
    return config;
  }

  const record = config as Record<string, unknown>;
  return {
    ...record,
    created_at: record.created_at ?? record.create_time,
    updated_at: record.updated_at ?? record.update_time
  };
}
