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

  return clusterInfoDetailResponseSchema.parse(envelope.data);
}
