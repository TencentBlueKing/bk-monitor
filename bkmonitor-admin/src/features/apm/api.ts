import { toBackendPagination } from '../../shared/schemas/pagination';
import { compactObject } from '../../shared/utils/format';
import type { AdminEnvironment } from '../environments/schemas';
import { kernelRpcClient } from '../kernel-rpc/client';
import {
  apmApplicationDetailResponseSchema,
  apmApplicationListResponseSchema,
  apmServiceListResponseSchema,
  type ApmApplicationDetailResponse,
  type ApmApplicationListQuery,
  type ApmApplicationListResponse,
  type ApmServiceListQuery,
  type ApmServiceListResponse
} from './schemas';

export async function listApmApplications(
  environment: AdminEnvironment,
  query: ApmApplicationListQuery
): Promise<ApmApplicationListResponse> {
  const envelope = await kernelRpcClient.call<unknown>({
    environment,
    operation: 'apm.application_list',
    params: compactObject({
      bk_tenant_id: query.bkTenantId,
      bk_biz_id: query.bkBizId,
      app_name: query.appName,
      status: query.status,
      bk_data_id: query.bkDataId,
      table_id: query.tableId,
      ...toBackendPagination(query)
    })
  });

  return apmApplicationListResponseSchema.parse(envelope.data);
}

export async function getApmApplicationDetail(
  environment: AdminEnvironment,
  params: { bkTenantId: string; applicationId: number; include?: string[] }
): Promise<ApmApplicationDetailResponse> {
  const envelope = await kernelRpcClient.call<unknown>({
    environment,
    operation: 'apm.application_detail',
    params: compactObject({
      bk_tenant_id: params.bkTenantId,
      application_id: params.applicationId,
      include: params.include
    })
  });

  return apmApplicationDetailResponseSchema.parse(envelope.data);
}

export async function listApmServices(
  environment: AdminEnvironment,
  query: ApmServiceListQuery
): Promise<ApmServiceListResponse> {
  const envelope = await kernelRpcClient.call<unknown>({
    environment,
    operation: 'apm.service_list',
    params: compactObject({
      bk_tenant_id: query.bkTenantId,
      application_id: query.applicationId,
      service_name: query.serviceName,
      kind: query.kind,
      ...toBackendPagination(query)
    })
  });

  return apmServiceListResponseSchema.parse(envelope.data);
}
