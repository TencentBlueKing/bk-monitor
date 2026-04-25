import type { KernelRpcCallOptions } from './client';
import {
  createMockEsRuntimeOverview,
  createMockEsSample,
  createMockEsStorageDetail,
  createMockClusterInfoDetail,
  createMockDatasourceDetail,
  createMockFieldList,
  createMockResultTableDetail,
  mockClusterInfos,
  mockDatasources,
  mockEsStorages,
  mockResultTables
} from './mockData';
import type { RpcEnvelope } from './schemas';

export function getMockResponse<TData>(options: KernelRpcCallOptions): RpcEnvelope<TData> {
  const data = resolveMockData(options) as TData;

  return {
    data,
    trace_id: `mock-${options.environment.id}-${Date.now()}`,
    warnings: ['当前使用 mock fallback，后端 RPC 可用后会自动切换到真实响应。'],
    meta: {
      environment_id: options.environment.id,
      operation: options.operation,
      safety_level: 'read'
    }
  };
}

function resolveMockData(options: KernelRpcCallOptions): unknown {
  switch (options.operation) {
    case 'tenant.list':
      return {
        items: [
          {
            id: 'system',
            name: 'system',
            display_name: 'system',
            source: 'mock',
            datasource_count: mockDatasources.length,
            result_table_count: mockResultTables.length
          }
        ],
        page: 1,
        page_size: 100,
        total: 1
      };
    case 'datasource.list':
      return {
        items: filterDatasources(options.params),
        page: Number(options.params.page ?? 1),
        page_size: Number(options.params.page_size ?? 20),
        total: filterDatasources(options.params).length
      };
    case 'datasource.detail':
      return createMockDatasourceDetail(Number(options.params.bk_data_id));
    case 'result_table.list':
      return {
        items: filterResultTables(options.params),
        page: Number(options.params.page ?? 1),
        page_size: Number(options.params.page_size ?? 20),
        total: filterResultTables(options.params).length
      };
    case 'result_table.detail':
      return createMockResultTableDetail(String(options.params.table_id));
    case 'result_table.field_list':
      return createMockFieldList(
        String(options.params.table_id),
        Number(options.params.page ?? 1),
        Number(options.params.page_size ?? 20),
        typeof options.params.field_name === 'string' ? options.params.field_name : undefined
      );
    case 'es_storage.list':
      return {
        items: filterEsStorages(options.params),
        page: Number(options.params.page ?? 1),
        page_size: Number(options.params.page_size ?? 20),
        total: filterEsStorages(options.params).length
      };
    case 'es_storage.detail':
      return createMockEsStorageDetail(String(options.params.table_id));
    case 'es_storage.runtime_overview':
      return createMockEsRuntimeOverview(String(options.params.table_id));
    case 'es_storage.sample':
      return createMockEsSample({
        tableId: String(options.params.table_id),
        index: String(options.params.index),
        timeField:
          typeof options.params.time_field === 'string' ? options.params.time_field : undefined
      });
    case 'cluster_info.list':
      return {
        items: filterClusterInfos(options.params),
        page: Number(options.params.page ?? 1),
        page_size: Number(options.params.page_size ?? 20),
        total: filterClusterInfos(options.params).length
      };
    case 'cluster_info.detail':
      return createMockClusterInfoDetail(Number(options.params.cluster_id));
  }
}

function filterDatasources(params: Record<string, unknown>) {
  const page = Number(params.page ?? 1);
  const pageSize = Number(params.page_size ?? 20);
  const filtered = mockDatasources.filter((item) => {
    if (typeof params.bk_data_id === 'number' && item.bk_data_id !== params.bk_data_id) {
      return false;
    }

    if (typeof params.data_name === 'string' && !item.data_name.includes(params.data_name)) {
      return false;
    }

    if (typeof params.table_id === 'string') {
      return item.bk_data_id === 50020
        ? params.table_id.includes('bklog')
        : params.table_id.includes('time_series');
    }

    return true;
  });

  return filtered.slice((page - 1) * pageSize, page * pageSize);
}

function filterResultTables(params: Record<string, unknown>) {
  const page = Number(params.page ?? 1);
  const pageSize = Number(params.page_size ?? 20);
  const filtered = mockResultTables.filter((item) => {
    if (typeof params.table_id === 'string' && !item.table_id.includes(params.table_id)) {
      return false;
    }

    if (typeof params.bk_data_id === 'number') {
      return params.bk_data_id === 50020 ? item.table_id === '3_bklog.demo' : item.bk_biz_id === 2;
    }

    if (typeof params.data_label === 'string' && !item.data_label?.includes(params.data_label)) {
      return false;
    }

    return true;
  });

  return filtered.slice((page - 1) * pageSize, page * pageSize);
}

function filterEsStorages(params: Record<string, unknown>) {
  const page = Number(params.page ?? 1);
  const pageSize = Number(params.page_size ?? 20);
  const filtered = mockEsStorages.filter((item) => {
    if (
      typeof params.table_id === 'string' &&
      !item.table_id.includes(params.table_id) &&
      !item.origin_table_id?.includes(params.table_id)
    ) {
      return false;
    }

    if (typeof params.data_label === 'string' && item.result_table?.data_label !== params.data_label) {
      return false;
    }

    if (typeof params.table_kind === 'string' && item.table_kind !== params.table_kind) {
      return false;
    }

    if (
      typeof params.storage_cluster_id === 'number' &&
      item.storage_cluster_id !== params.storage_cluster_id
    ) {
      return false;
    }

    if (typeof params.source_type === 'string' && item.source_type !== params.source_type) {
      return false;
    }

    if (
      typeof params.need_create_index === 'boolean' &&
      item.need_create_index !== params.need_create_index
    ) {
      return false;
    }

    return true;
  });

  return filtered.slice((page - 1) * pageSize, page * pageSize);
}

function filterClusterInfos(params: Record<string, unknown>) {
  const page = Number(params.page ?? 1);
  const pageSize = Number(params.page_size ?? 20);
  const filtered = mockClusterInfos.filter((item) => {
    if (typeof params.cluster_name === 'string' && !item.cluster_name.includes(params.cluster_name)) {
      return false;
    }

    if (typeof params.cluster_type === 'string' && item.cluster_type !== params.cluster_type) {
      return false;
    }

    return true;
  });

  return filtered.slice((page - 1) * pageSize, page * pageSize);
}
