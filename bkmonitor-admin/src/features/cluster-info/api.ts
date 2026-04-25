import type { AdminEnvironment } from '../environments/schemas';
import { kernelRpcClient } from '../kernel-rpc/client';
import { toBackendPagination } from '../../shared/schemas/pagination';
import { compactObject } from '../../shared/utils/format';
import {
  clusterInfoDetailResponseSchema,
  clusterInfoListResponseSchema,
  type ClusterInfoDetailResponse,
  type ClusterInfoListQuery,
  type ClusterInfoListResponse
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
