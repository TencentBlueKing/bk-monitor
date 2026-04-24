import type { AdminEnvironment } from '../environments/schemas';
import { kernelRpcClient } from '../kernel-rpc/client';
import {
  datasourceDetailResponseSchema,
  datasourceListResponseSchema,
  type DataSourceDetailResponse,
  type DataSourceListQuery,
  type DataSourceListResponse
} from './schemas';
import { compactObject } from '../../shared/utils/format';
import { toBackendPagination } from '../../shared/schemas/pagination';

export async function listDatasources(
  environment: AdminEnvironment,
  query: DataSourceListQuery
): Promise<DataSourceListResponse> {
  const envelope = await kernelRpcClient.call<unknown>({
    environment,
    operation: 'datasource.list',
    params: compactObject({
      bk_tenant_id: query.bkTenantId,
      bk_data_id: query.bkDataId,
      data_name: query.dataName,
      created_from: query.createdFrom,
      source_label: query.sourceLabel,
      type_label: query.typeLabel,
      is_enable: query.isEnable,
      space_uid: query.spaceUid,
      table_id: query.tableId,
      ...toBackendPagination(query)
    })
  });

  return datasourceListResponseSchema.parse(envelope.data);
}

export async function getDatasourceDetail(
  environment: AdminEnvironment,
  bkTenantId: string,
  bkDataId: number
): Promise<DataSourceDetailResponse> {
  const envelope = await kernelRpcClient.call<unknown>({
    environment,
    operation: 'datasource.detail',
    params: {
      bk_tenant_id: bkTenantId,
      bk_data_id: bkDataId,
      include: ['options', 'spaces', 'result_tables', 'data_id_config']
    }
  });

  return datasourceDetailResponseSchema.parse(envelope.data);
}
