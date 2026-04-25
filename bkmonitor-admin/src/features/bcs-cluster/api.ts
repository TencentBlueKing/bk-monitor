import type { AdminEnvironment } from '../environments/schemas';
import { kernelRpcClient } from '../kernel-rpc/client';
import { toBackendPagination } from '../../shared/schemas/pagination';
import { compactObject } from '../../shared/utils/format';
import {
  bcsClusterDetailResponseSchema,
  bcsClusterListResponseSchema,
  type BcsClusterDetailResponse,
  type BcsClusterListQuery,
  type BcsClusterListResponse
} from './schemas';

export async function listBcsClusters(
  environment: AdminEnvironment,
  query: BcsClusterListQuery
): Promise<BcsClusterListResponse> {
  const envelope = await kernelRpcClient.call<unknown>({
    environment,
    operation: 'bcs_cluster.list',
    params: compactObject({
      bk_tenant_id: query.bkTenantId,
      cluster_id: query.clusterId,
      bk_biz_id: query.bkBizId,
      status: query.status && query.status.length > 0 ? query.status : undefined,
      ...toBackendPagination(query)
    })
  });

  return bcsClusterListResponseSchema.parse(envelope.data);
}

export async function getBcsClusterDetail(
  environment: AdminEnvironment,
  bkTenantId: string,
  clusterId: string
): Promise<BcsClusterDetailResponse> {
  const envelope = await kernelRpcClient.call<unknown>({
    environment,
    operation: 'bcs_cluster.detail',
    params: {
      bk_tenant_id: bkTenantId,
      cluster_id: clusterId
    }
  });

  return bcsClusterDetailResponseSchema.parse(envelope.data);
}
