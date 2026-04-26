import { toBackendPagination } from '../../shared/schemas/pagination';
import { compactObject } from '../../shared/utils/format';
import type { AdminEnvironment } from '../environments/schemas';
import { kernelRpcClient } from '../kernel-rpc/client';
import {
  customReportDetailResponseSchema,
  customReportListResponseSchema,
  customReportMetricListResponseSchema,
  type CustomReportDetailResponse,
  type CustomReportListQuery,
  type CustomReportListResponse,
  type CustomReportMetricListQuery,
  type CustomReportMetricListResponse,
  type CustomReportType
} from './schemas';

export async function listCustomReports(
  environment: AdminEnvironment,
  query: CustomReportListQuery
): Promise<CustomReportListResponse> {
  const envelope = await kernelRpcClient.call<unknown>({
    environment,
    operation: 'custom_report.list',
    params: compactObject({
      bk_tenant_id: query.bkTenantId,
      report_type: query.reportType,
      bk_biz_id: query.bkBizId,
      bk_data_id: query.bkDataId,
      table_id: query.tableId,
      group_name: query.groupName,
      created_from: query.createdFrom,
      has_apm: query.hasApm,
      ...toBackendPagination(query)
    })
  });

  return customReportListResponseSchema.parse(envelope.data);
}

export async function getCustomReportDetail(
  environment: AdminEnvironment,
  params: { bkTenantId: string; reportType: CustomReportType; groupId: number; include?: string[] }
): Promise<CustomReportDetailResponse> {
  const envelope = await kernelRpcClient.call<unknown>({
    environment,
    operation: 'custom_report.detail',
    params: compactObject({
      bk_tenant_id: params.bkTenantId,
      report_type: params.reportType,
      group_id: params.groupId,
      include: params.include
    })
  });

  return customReportDetailResponseSchema.parse(envelope.data);
}

export async function listCustomReportMetrics(
  environment: AdminEnvironment,
  query: CustomReportMetricListQuery
): Promise<CustomReportMetricListResponse> {
  const envelope = await kernelRpcClient.call<unknown>({
    environment,
    operation: 'custom_report.metric_list',
    params: compactObject({
      bk_tenant_id: query.bkTenantId,
      group_id: query.groupId,
      field_name: query.fieldName,
      is_active: query.isActive,
      ...toBackendPagination(query)
    })
  });

  return customReportMetricListResponseSchema.parse(envelope.data);
}
