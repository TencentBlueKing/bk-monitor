import { toBackendPagination } from '../../shared/schemas/pagination';
import { compactObject } from '../../shared/utils/format';
import type { AdminEnvironment } from '../environments/schemas';
import { kernelRpcClient } from '../kernel-rpc/client';
import {
  esRuntimeOverviewResponseSchema,
  esSampleResponseSchema,
  esStorageDetailResponseSchema,
  esStorageListResponseSchema,
  type EsRuntimeOverviewResponse,
  type EsSampleResponse,
  type EsStorageDetailResponse,
  type EsStorageListQuery,
  type EsStorageListResponse
} from './schemas';

export async function listEsStorages(
  environment: AdminEnvironment,
  query: EsStorageListQuery
): Promise<EsStorageListResponse> {
  const envelope = await kernelRpcClient.call<unknown>({
    environment,
    operation: 'es_storage.list',
    params: compactObject({
      bk_tenant_id: query.bkTenantId,
      table_id: query.tableId,
      data_label: query.dataLabel,
      table_kind: query.tableKind,
      storage_cluster_id: query.storageClusterId,
      source_type: query.sourceType,
      need_create_index: query.needCreateIndex,
      ordering: query.ordering,
      ...toBackendPagination(query)
    })
  });

  return esStorageListResponseSchema.parse(envelope.data);
}

export async function getEsStorageDetail(
  environment: AdminEnvironment,
  bkTenantId: string,
  tableId: string
): Promise<EsStorageDetailResponse> {
  const envelope = await kernelRpcClient.call<unknown>({
    environment,
    operation: 'es_storage.detail',
    params: {
      bk_tenant_id: bkTenantId,
      table_id: tableId,
      include: ['relations']
    }
  });

  return esStorageDetailResponseSchema.parse(
    normalizeEsStorageDetailPayload(envelope.data, envelope.warnings)
  );
}

export async function getEsRuntimeOverview(
  environment: AdminEnvironment,
  params: { bkTenantId: string; tableId: string; index?: string }
): Promise<EsRuntimeOverviewResponse> {
  const envelope = await kernelRpcClient.call<unknown>({
    environment,
    operation: 'es_storage.runtime_overview',
    params: compactObject({
      bk_tenant_id: params.bkTenantId,
      table_id: params.tableId,
      include: ['indices', 'aliases', 'mapping'],
      index: params.index
    })
  });

  return esRuntimeOverviewResponseSchema.parse(
    normalizeEsRuntimeOverviewPayload(envelope.data, envelope.warnings)
  );
}

export async function sampleEsStorage(
  environment: AdminEnvironment,
  params: { bkTenantId: string; tableId: string; index: string; timeField?: string }
): Promise<EsSampleResponse> {
  const envelope = await kernelRpcClient.call<unknown>({
    environment,
    operation: 'es_storage.sample',
    params: compactObject({
      bk_tenant_id: params.bkTenantId,
      table_id: params.tableId,
      index: params.index,
      time_field: params.timeField
    })
  });

  return esSampleResponseSchema.parse(normalizeEsSamplePayload(envelope.data, envelope.warnings));
}

function normalizeEsStorageDetailPayload(payload: unknown, warnings: unknown[] = []): unknown {
  if (!isRecord(payload)) {
    return payload;
  }

  return {
    ...payload,
    field_aliases: normalizeFieldAliases(payload.field_aliases),
    warnings: normalizeWarnings(warnings)
  };
}

function normalizeEsRuntimeOverviewPayload(payload: unknown, warnings: unknown[] = []): unknown {
  if (!isRecord(payload)) {
    return payload;
  }

  return {
    ...payload,
    index_pattern: normalizeIndexPattern(payload.index_pattern),
    indices: normalizeRuntimeIndices(payload.indices),
    aliases: payload.aliases ?? [],
    field_aliases: normalizeFieldAliases(payload.field_aliases),
    warnings: normalizeWarnings(warnings)
  };
}

function normalizeEsSamplePayload(payload: unknown, warnings: unknown[] = []): unknown {
  if (!isRecord(payload)) {
    return payload;
  }

  return {
    ...payload,
    warnings: normalizeWarnings(warnings)
  };
}

function normalizeWarnings(warnings: unknown[]): string[] {
  return warnings.map((warning) => {
    if (typeof warning === 'string') {
      return warning;
    }

    if (isRecord(warning) && typeof warning.message === 'string') {
      return warning.message;
    }

    return String(warning);
  });
}

function normalizeFieldAliases(value: unknown): unknown[] {
  if (Array.isArray(value)) {
    return value;
  }

  if (isRecord(value)) {
    const items = value.items;
    return Array.isArray(items) ? items : [];
  }

  return [];
}

function normalizeIndexPattern(value: unknown): string | null {
  if (typeof value === 'string') {
    return value;
  }

  if (isRecord(value)) {
    for (const key of ['effective', 'v2', 'v1']) {
      const pattern = value[key];
      if (typeof pattern === 'string' && pattern) {
        return pattern;
      }
    }
  }

  return null;
}

function normalizeRuntimeIndices(value: unknown): unknown[] {
  if (Array.isArray(value)) {
    return value;
  }

  if (isRecord(value) && Array.isArray(value.items)) {
    return value.items.map((item) => normalizeRuntimeIndexItem(item));
  }

  return [];
}

function normalizeRuntimeIndexItem(value: unknown): Record<string, unknown> {
  if (!isRecord(value)) {
    return { index: String(value ?? '') };
  }

  const stats = isRecord(value.stats) ? value.stats : {};
  const total = isRecord(stats.total) ? stats.total : {};
  const docs = isRecord(total.docs) ? total.docs : {};
  const store = isRecord(total.store) ? total.store : {};

  return {
    ...value,
    docs_count: value.docs_count ?? docs.count,
    store_size: value.store_size ?? formatMaybeNumber(store.size_in_bytes)
  };
}

function formatMaybeNumber(value: unknown): unknown {
  return typeof value === 'number' ? String(value) : value;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}
