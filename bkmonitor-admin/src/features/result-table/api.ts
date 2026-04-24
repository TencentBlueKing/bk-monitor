import { toBackendPagination } from '../../shared/schemas/pagination';
import { compactObject } from '../../shared/utils/format';
import type { AdminEnvironment } from '../environments/schemas';
import { kernelRpcClient } from '../kernel-rpc/client';
import {
  resultTableDetailResponseSchema,
  resultTableFieldListResponseSchema,
  resultTableListResponseSchema,
  type ResultTableDetailResponse,
  type ResultTableFieldListQuery,
  type ResultTableFieldListResponse,
  type ResultTableListQuery,
  type ResultTableListResponse
} from './schemas';

export async function listResultTables(
  environment: AdminEnvironment,
  query: ResultTableListQuery
): Promise<ResultTableListResponse> {
  const envelope = await kernelRpcClient.call<unknown>({
    environment,
    operation: 'result_table.list',
    params: compactObject({
      bk_tenant_id: query.bkTenantId,
      table_id: query.tableId,
      table_name_zh: query.tableNameZh,
      bk_biz_id: query.bkBizId,
      bk_data_id: query.bkDataId,
      data_label: query.dataLabel,
      label: query.label,
      schema_type: query.schemaType,
      default_storage: query.defaultStorage,
      is_enable: query.isEnable,
      is_deleted: query.isDeleted,
      is_builtin: query.isBuiltin,
      ...toBackendPagination(query)
    })
  });

  return resultTableListResponseSchema.parse(envelope.data);
}

export async function getResultTableDetail(
  environment: AdminEnvironment,
  bkTenantId: string,
  tableId: string
): Promise<ResultTableDetailResponse> {
  const envelope = await kernelRpcClient.call<unknown>({
    environment,
    operation: 'result_table.detail',
    params: {
      bk_tenant_id: bkTenantId,
      table_id: tableId,
      include: ['custom_groups', 'datasources', 'options', 'storages', 'vm_records']
    }
  });

  return resultTableDetailResponseSchema.parse(normalizeResultTableDetailPayload(envelope.data));
}

export async function listResultTableFields(
  environment: AdminEnvironment,
  query: ResultTableFieldListQuery
): Promise<ResultTableFieldListResponse> {
  const envelope = await kernelRpcClient.call<unknown>({
    environment,
    operation: 'result_table.field_list',
    params: compactObject({
      bk_tenant_id: query.bkTenantId,
      table_id: query.tableId,
      field_name: query.fieldName,
      field_type: query.fieldType,
      tag: query.tag,
      is_config_by_user: query.isConfigByUser,
      is_disabled: query.isDisabled,
      has_option: query.hasOption,
      ...toBackendPagination(query)
    })
  });

  return resultTableFieldListResponseSchema.parse(envelope.data);
}

function normalizeResultTableDetailPayload(payload: unknown): unknown {
  if (!isRecord(payload)) {
    return payload;
  }

  const resultTable = isRecord(payload.result_table) ? payload.result_table : {};
  const summary = isRecord(payload.summary) ? payload.summary : {};
  const storages = isRecord(payload.storages) ? payload.storages : {};
  const esStorages: unknown[] = Array.isArray(storages.es) ? storages.es : [];
  const esStorage: unknown = esStorages[0] ?? null;
  const accessVmRecords: unknown[] = Array.isArray(payload.access_vm_records)
    ? payload.access_vm_records
    : [];

  return {
    ...payload,
    result_table: {
      ...resultTable,
      field_count: summary.field_count,
      datasource_count: summary.datasource_count,
      has_es_storage: Boolean(esStorage),
      has_vm_record: accessVmRecords.length > 0
    },
    options: Array.isArray(payload.options) ? payload.options : [],
    datasources: Array.isArray(payload.datasources) ? payload.datasources : [],
    custom_groups: Array.isArray(payload.custom_groups) ? payload.custom_groups : [],
    es_storage: esStorage,
    vm_record: accessVmRecords[0] ?? null
  };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}
