import type { KernelRpcCallOptions } from './client';
import {
  createMockEsRuntimeOverview,
  createMockEsSample,
  createMockEsStorageDetail,
  createMockQueryRoute,
  createMockClusterInfoDetail,
  createMockComponentConfig,
  createMockDatasourceDetail,
  createMockFieldList,
  createMockResultTableDetail,
  createMockBcsClusterDetail,
  createMockComponentDetail,
  createMockClusterConfigDetail,
  createMockDatalinkDetail,
  createMockDatalinkComponentConfig,
  createMockApmApplicationDetail,
  createMockApmServiceList,
  createMockCustomReportDetail,
  createMockCustomReportMetricList,
  mockBcsClusters,
  mockApmApplications,
  mockClusterInfos,
  mockClusterConfigs,
  mockCustomReports,
  mockDatalinkComponents,
  mockDataLinks,
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
    case 'cluster_info.component_config':
      return createMockComponentConfig({
        clusterId: Number(options.params.cluster_id),
        namespace: String(options.params.namespace),
        kind: String(options.params.kind),
        name: String(options.params.name)
      });
    case 'datalink.component_list':
      return {
        items: filterDatalinkComponents(options.params),
        page: Number(options.params.page ?? 1),
        page_size: Number(options.params.page_size ?? 20),
        total: filterDatalinkComponents(options.params).length
      };
    case 'datalink.component_detail':
      return createMockComponentDetail(
        String(options.params.kind),
        String(options.params.namespace),
        String(options.params.name)
      );
    case 'datalink.component_config':
    case 'datalink.datalink_component_config':
      return createMockDatalinkComponentConfig(
        String(options.params.namespace),
        String(options.params.kind),
        String(options.params.name)
      );
    case 'datalink.cluster_config_list':
      return {
        items: filterClusterConfigs(options.params),
        page: Number(options.params.page ?? 1),
        page_size: Number(options.params.page_size ?? 20),
        total: filterClusterConfigs(options.params).length
      };
    case 'datalink.cluster_config_detail':
      return createMockClusterConfigDetail(
        String(options.params.kind),
        String(options.params.namespace),
        String(options.params.name)
      );
    case 'datalink.cluster_config_component_config':
      return createMockDatalinkComponentConfig(
        String(options.params.namespace),
        String(options.params.kind),
        String(options.params.name)
      );
    case 'datalink.datalink_list':
      return {
        items: filterDataLinks(options.params),
        page: Number(options.params.page ?? 1),
        page_size: Number(options.params.page_size ?? 20),
        total: filterDataLinks(options.params).length
      };
    case 'datalink.datalink_detail':
      return createMockDatalinkDetail(String(options.params.data_link_name));
    case 'datasource.data_id_config.component_config':
      return createMockComponentConfig({
        clusterId: 0,
        namespace: String(options.params.namespace),
        kind: 'DataId',
        name: String(options.params.name)
      });
    case 'query_route.query':
      return createMockQueryRoute(options.params);
    case 'query_route.refresh':
      return {
        ...createMockQueryRoute(options.params),
        refreshed: true,
        targets: ['space_to_result_table', 'data_label_to_result_table', 'result_table_detail'],
        message: 'mock 已刷新相关路由，会写 Redis 并 publish 通知 unify-query。'
      };
    case 'bcs_cluster.list':
      return {
        items: filterBcsClusters(options.params),
        page: Number(options.params.page ?? 1),
        page_size: Number(options.params.page_size ?? 20),
        total: filterBcsClusters(options.params).length
      };
    case 'bcs_cluster.detail':
      return createMockBcsClusterDetail(String(options.params.cluster_id));
    case 'custom_report.list':
      return {
        items: filterCustomReports(options.params),
        page: Number(options.params.page ?? 1),
        page_size: Number(options.params.page_size ?? 20),
        total: filterCustomReports(options.params).length
      };
    case 'custom_report.detail':
      return createMockCustomReportDetail(
        String(options.params.report_type),
        Number(options.params.group_id)
      );
    case 'custom_report.metric_list':
      return createMockCustomReportMetricList(
        Number(options.params.group_id),
        Number(options.params.page ?? 1),
        Number(options.params.page_size ?? 20),
        typeof options.params.field_name === 'string' ? options.params.field_name : undefined
      );
    case 'apm.application_list':
      return {
        items: filterApmApplications(options.params),
        page: Number(options.params.page ?? 1),
        page_size: Number(options.params.page_size ?? 20),
        total: filterApmApplications(options.params).length
      };
    case 'apm.application_detail':
      return createMockApmApplicationDetail(Number(options.params.application_id));
    case 'apm.service_list':
      return createMockApmServiceList(
        Number(options.params.application_id),
        Number(options.params.page ?? 1),
        Number(options.params.page_size ?? 20),
        typeof options.params.service_name === 'string' ? options.params.service_name : undefined
      );
    case 'apm.topo':
      return createMockApmApplicationDetail(Number(options.params.application_id)).topo_summary;
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

    if (
      typeof params.data_label === 'string' &&
      item.result_table?.data_label !== params.data_label
    ) {
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
    if (
      typeof params.cluster_name === 'string' &&
      !item.cluster_name.includes(params.cluster_name)
    ) {
      return false;
    }

    if (typeof params.cluster_type === 'string' && item.cluster_type !== params.cluster_type) {
      return false;
    }

    return true;
  });

  return filtered.slice((page - 1) * pageSize, page * pageSize);
}

function filterBcsClusters(params: Record<string, unknown>) {
  const page = Number(params.page ?? 1);
  const pageSize = Number(params.page_size ?? 20);
  const filtered = mockBcsClusters.filter((item) => {
    if (typeof params.cluster_id === 'string' && !item.cluster_id.includes(params.cluster_id)) {
      return false;
    }

    if (typeof params.bk_biz_id === 'number' && item.bk_biz_id !== params.bk_biz_id) {
      return false;
    }

    return true;
  });

  return filtered.slice((page - 1) * pageSize, page * pageSize);
}

function filterDatalinkComponents(params: Record<string, unknown>) {
  const page = Number(params.page ?? 1);
  const pageSize = Number(params.page_size ?? 20);
  const kind = typeof params.kind === 'string' ? params.kind : undefined;
  let filtered = kind
    ? mockDatalinkComponents.filter((item) => item.kind === kind)
    : mockDatalinkComponents;

  if (typeof params.namespace === 'string') {
    filtered = filtered.filter((item) => item.namespace === params.namespace);
  }
  if (typeof params.search === 'string') {
    filtered = filtered.filter((item) => item.name.includes(params.search as string));
  }
  if (typeof params.status === 'string') {
    filtered = filtered.filter((item) => item.status === params.status);
  }
  if (typeof params.bk_data_id === 'number') {
    filtered = filtered.filter((item) => item.bk_data_id === params.bk_data_id);
  }
  if (typeof params.has_data_link === 'boolean') {
    filtered = filtered.filter((item) => params.has_data_link !== Boolean(item.data_link_name));
  }

  return filtered.slice((page - 1) * pageSize, page * pageSize);
}

function filterClusterConfigs(params: Record<string, unknown>) {
  const page = Number(params.page ?? 1);
  const pageSize = Number(params.page_size ?? 20);
  let filtered = mockClusterConfigs;

  if (typeof params.kind === 'string') {
    filtered = filtered.filter((item) => item.kind === params.kind);
  }
  if (typeof params.namespace === 'string') {
    filtered = filtered.filter((item) => item.namespace === params.namespace);
  }
  if (typeof params.search === 'string') {
    filtered = filtered.filter((item) => item.name.includes(params.search as string));
  }

  return filtered.slice((page - 1) * pageSize, page * pageSize);
}

function filterDataLinks(params: Record<string, unknown>) {
  const page = Number(params.page ?? 1);
  const pageSize = Number(params.page_size ?? 20);
  let filtered = mockDataLinks;

  if (typeof params.namespace === 'string') {
    filtered = filtered.filter((item) => item.namespace === params.namespace);
  }
  if (typeof params.search === 'string') {
    filtered = filtered.filter((item) => item.data_link_name.includes(params.search as string));
  }
  if (typeof params.data_link_strategy === 'string') {
    filtered = filtered.filter((item) => item.data_link_strategy === params.data_link_strategy);
  }
  if (typeof params.bk_data_id === 'number') {
    filtered = filtered.filter((item) => item.bk_data_id === params.bk_data_id);
  }

  return filtered.slice((page - 1) * pageSize, page * pageSize);
}

function filterCustomReports(params: Record<string, unknown>) {
  const page = Number(params.page ?? 1);
  const pageSize = Number(params.page_size ?? 20);
  const filtered = mockCustomReports.filter((item) => {
    if (typeof params.report_type === 'string' && item.report_type !== params.report_type) {
      return false;
    }
    if (typeof params.bk_biz_id === 'number' && item.bk_biz_id !== params.bk_biz_id) {
      return false;
    }
    if (typeof params.bk_data_id === 'number' && item.bk_data_id !== params.bk_data_id) {
      return false;
    }
    if (typeof params.table_id === 'string' && !item.table_id?.includes(params.table_id)) {
      return false;
    }
    if (typeof params.group_name === 'string' && !item.group_name.includes(params.group_name)) {
      return false;
    }
    if (typeof params.created_from === 'string' && item.created_from !== params.created_from) {
      return false;
    }
    if (typeof params.has_apm === 'boolean') {
      return params.has_apm ? item.apm_application_count > 0 : item.apm_application_count === 0;
    }
    return true;
  });

  return filtered.slice((page - 1) * pageSize, page * pageSize);
}

function filterApmApplications(params: Record<string, unknown>) {
  const page = Number(params.page ?? 1);
  const pageSize = Number(params.page_size ?? 20);
  const filtered = mockApmApplications.filter((item) => {
    if (typeof params.bk_biz_id === 'number' && item.bk_biz_id !== params.bk_biz_id) {
      return false;
    }
    if (typeof params.app_name === 'string' && !item.app_name.includes(params.app_name)) {
      return false;
    }
    if (typeof params.status === 'string' && item.status !== params.status) {
      return false;
    }
    if (typeof params.bk_data_id === 'number') {
      return [
        item.metric_data_id,
        item.trace_data_id,
        item.log_data_id,
        item.profile_data_id
      ].includes(params.bk_data_id);
    }
    if (typeof params.table_id === 'string') {
      return mockCustomReports.some(
        (report) =>
          report.apm_application_count > 0 &&
          report.bk_biz_id === item.bk_biz_id &&
          report.table_id?.includes(params.table_id as string)
      );
    }
    return true;
  });

  return filtered.slice((page - 1) * pageSize, page * pageSize);
}
