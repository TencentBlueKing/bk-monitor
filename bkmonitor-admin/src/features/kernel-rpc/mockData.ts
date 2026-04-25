import type { DataSourceDetailResponse, DataSourceListResponse } from '../datasource/schemas';
import type {
  ClusterInfoDetailResponse,
  ClusterInfoListResponse,
  ComponentConfigResponse
} from '../cluster-info/schemas';
import type {
  EsRuntimeOverviewResponse,
  EsSampleResponse,
  EsStorageDetailResponse,
  EsStorageListResponse
} from '../es-storage/schemas';
import type {
  ResultTableDetailResponse,
  ResultTableFieldListResponse,
  ResultTableListResponse
} from '../result-table/schemas';
import type { QueryRouteResponse } from '../query-route/schemas';
import type { BcsClusterListResponse, BcsClusterDetailResponse } from '../bcs-cluster/schemas';

export const mockDatasources: DataSourceListResponse['items'] = [
  {
    bk_data_id: 50010,
    data_name: 'custom_metric_demo',
    data_description: '自定义指标接入示例',
    bk_tenant_id: 'system',
    type_label: 'time_series',
    source_label: 'bk_monitor',
    created_from: 'bkmonitor',
    is_enable: true,
    is_custom_source: true,
    is_platform_data_id: false,
    space_uid: 'bkcc__2',
    mq_cluster_id: 1,
    mq_config_id: 101,
    kafka_cluster: {
      cluster_id: 1,
      cluster_name: 'default-kafka',
      display_name: '默认 Kafka 集群',
      cluster_type: 'kafka',
      is_default_cluster: true,
      registered_system: '_default',
      label: 'default'
    },
    transfer_cluster_id: 'default',
    create_time: '2026-04-18 10:00:00',
    last_modify_time: '2026-04-22 11:30:00',
    result_table_count: 2,
    space_count: 1,
    option_count: 3,
    has_data_id_config: false
  },
  {
    bk_data_id: 50020,
    data_name: 'bkdata_link_demo',
    data_description: 'bkdata 链路接入示例',
    bk_tenant_id: 'system',
    type_label: 'log',
    source_label: 'bk_data',
    created_from: 'bkdata',
    is_enable: true,
    is_custom_source: false,
    is_platform_data_id: true,
    space_uid: 'bkcc__3',
    mq_cluster_id: 2,
    mq_config_id: 102,
    kafka_cluster: {
      cluster_id: 2,
      cluster_name: 'bkdata-kafka',
      display_name: 'BKData Kafka 集群',
      cluster_type: 'kafka',
      is_default_cluster: false,
      registered_system: 'bkdata',
      label: 'bkdata'
    },
    transfer_cluster_id: 'transfer-bkdata',
    create_time: '2026-04-19 09:00:00',
    last_modify_time: '2026-04-23 17:30:00',
    result_table_count: 1,
    space_count: 2,
    option_count: 2,
    has_data_id_config: true
  }
];

export const mockResultTables: ResultTableListResponse['items'] = [
  {
    table_id: '2_bkmonitor_time_series.__default__',
    table_name_zh: '默认自定义指标',
    bk_tenant_id: 'system',
    bk_biz_id: 2,
    label: 'custom',
    data_label: 'custom_metric_demo',
    schema_type: 'free',
    default_storage: 'influxdb',
    is_custom_table: true,
    is_builtin: false,
    is_enable: true,
    is_deleted: false,
    create_time: '2026-04-18 10:01:00',
    last_modify_time: '2026-04-22 11:32:00',
    field_count: 128,
    datasource_count: 1,
    has_es_storage: false,
    has_vm_record: true,
    custom_group_type: 'time_series'
  },
  {
    table_id: '3_bklog.demo',
    table_name_zh: '日志示例表',
    bk_tenant_id: 'system',
    bk_biz_id: 3,
    label: 'log',
    data_label: 'bkdata_link_demo',
    schema_type: 'fixed',
    default_storage: 'es',
    is_custom_table: false,
    is_builtin: false,
    is_enable: true,
    is_deleted: false,
    create_time: '2026-04-19 09:02:00',
    last_modify_time: '2026-04-23 17:33:00',
    field_count: 42,
    datasource_count: 1,
    has_es_storage: true,
    has_vm_record: false,
    custom_group_type: 'log'
  }
];

export const mockEsStorages: EsStorageListResponse['items'] = [
  {
    id: 1,
    table_id: '3_bklog.demo',
    origin_table_id: null,
    table_kind: 'physical',
    bk_tenant_id: 'system',
    storage_cluster_id: 3,
    storage_cluster: {
      cluster_id: 3,
      cluster_name: 'default-es',
      display_name: '默认 ES 集群',
      cluster_type: 'elasticsearch'
    },
    result_table: {
      table_id: '3_bklog.demo',
      table_name_zh: '日志示例表',
      bk_biz_id: 3,
      data_label: 'bkdata_link_demo',
      default_storage: 'es',
      is_enable: true,
      is_deleted: false
    },
    physical_table: null,
    virtual_table_count: 1,
    retention: 30,
    slice_size: 500,
    slice_gap: 120,
    date_format: '%Y%m%d',
    time_zone: 'UTC',
    source_type: 'log',
    index_set: '3_bklog_demo',
    need_create_index: true,
    archive_index_days: 0,
    warm_phase_days: 7,
    create_time: '2026-04-19 09:05:00',
    last_modify_time: '2026-04-23 17:35:00'
  },
  {
    id: 2,
    table_id: '3_bklog.demo_virtual',
    origin_table_id: '3_bklog.demo',
    table_kind: 'virtual',
    bk_tenant_id: 'system',
    storage_cluster_id: 3,
    storage_cluster: {
      cluster_id: 3,
      cluster_name: 'default-es',
      display_name: '默认 ES 集群',
      cluster_type: 'elasticsearch'
    },
    result_table: {
      table_id: '3_bklog.demo_virtual',
      table_name_zh: '日志虚拟表',
      bk_biz_id: 3,
      data_label: 'bkdata_link_demo',
      default_storage: 'es',
      is_enable: true,
      is_deleted: false
    },
    physical_table: {
      table_id: '3_bklog.demo',
      exists: true
    },
    virtual_table_count: 0,
    retention: 30,
    slice_size: 500,
    slice_gap: 120,
    date_format: '%Y%m%d',
    time_zone: 'UTC',
    source_type: 'log',
    index_set: '3_bklog_demo_virtual',
    need_create_index: false,
    archive_index_days: 0,
    warm_phase_days: 0,
    create_time: '2026-04-20 10:00:00',
    last_modify_time: '2026-04-24 10:30:00'
  }
];

export const mockClusterInfos: ClusterInfoListResponse['items'] = [
  {
    cluster_id: 1,
    cluster_name: 'default-kafka',
    display_name: '默认 Kafka 集群',
    cluster_type: 'kafka',
    domain_name: 'kafka.service.local',
    port: 9092,
    version: '2.8',
    is_default_cluster: true,
    registered_system: '_default',
    label: 'default',
    description: 'mock kafka cluster',
    associated_datasources: 1,
    associated_storages: 0,
    create_time: '2026-04-18 10:00:00',
    last_modify_time: '2026-04-22 11:30:00'
  },
  {
    cluster_id: 3,
    cluster_name: 'default-es',
    display_name: '默认 ES 集群',
    cluster_type: 'elasticsearch',
    domain_name: 'es.service.local',
    port: 9200,
    version: '7.10',
    is_default_cluster: true,
    registered_system: '_default',
    label: 'default',
    description: 'mock elasticsearch cluster',
    associated_datasources: 0,
    associated_storages: mockEsStorages.length,
    create_time: '2026-04-19 09:00:00',
    last_modify_time: '2026-04-23 17:30:00'
  }
];

export const mockBcsClusters: BcsClusterListResponse['items'] = [
  {
    cluster_id: 'BCS-K8S-0001',
    bcs_api_cluster_id: 'BCS-API-0001',
    bk_biz_id: 2,
    project_id: 'project-alpha',
    status: 'running',
    bk_env: 'production',
    K8sMetricDataID: 50020,
    CustomMetricDataID: 51020,
    K8sEventDataID: 52020,
    CustomEventDataID: 53020,
    SystemLogDataID: 54020,
    CustomLogDataID: 55020,
    operator_ns: 'bcs-system-prod',
    trace_data_id: 56020,
    create_time: '2026-04-11 08:00:00',
    last_modify_time: '2026-04-21 14:30:00'
  },
  {
    cluster_id: 'BCS-K8S-0002',
    bcs_api_cluster_id: 'BCS-API-0002',
    bk_biz_id: 3,
    project_id: 'project-beta',
    status: 'running',
    bk_env: 'staging',
    K8sMetricDataID: 50030,
    CustomMetricDataID: 51030,
    K8sEventDataID: 52030,
    CustomEventDataID: 53030,
    SystemLogDataID: 54030,
    CustomLogDataID: 55030,
    operator_ns: 'bcs-system-staging',
    trace_data_id: 56030,
    create_time: '2026-04-12 08:00:00',
    last_modify_time: '2026-04-22 14:30:00'
  },
  {
    cluster_id: 'BCS-K8S-0003',
    bcs_api_cluster_id: 'BCS-API-0003',
    bk_biz_id: 4,
    project_id: 'project-gamma',
    status: 'abnormal',
    bk_env: 'development',
    K8sMetricDataID: 50040,
    CustomMetricDataID: 51040,
    K8sEventDataID: 52040,
    CustomEventDataID: 53040,
    SystemLogDataID: 54040,
    CustomLogDataID: 0,
    operator_ns: 'bcs-system-dev',
    trace_data_id: 56040,
    create_time: '2026-04-13 08:00:00',
    last_modify_time: '2026-04-23 14:30:00'
  },
  {
    cluster_id: 'BCS-K8S-0004',
    bcs_api_cluster_id: 'BCS-API-0004',
    bk_biz_id: 5,
    project_id: 'project-prod',
    status: 'running',
    bk_env: 'production',
    K8sMetricDataID: 50050,
    CustomMetricDataID: 51050,
    K8sEventDataID: 52050,
    CustomEventDataID: 53050,
    SystemLogDataID: 0,
    CustomLogDataID: 0,
    operator_ns: 'bcs-system-prod',
    trace_data_id: 0,
    create_time: '2026-04-14 08:00:00',
    last_modify_time: '2026-04-24 14:30:00'
  },
  {
    cluster_id: 'BCS-K8S-0005',
    bcs_api_cluster_id: 'BCS-API-0005',
    bk_biz_id: 2,
    project_id: 'project-dev',
    status: 'deleted',
    bk_env: 'staging',
    K8sMetricDataID: 50060,
    CustomMetricDataID: 51060,
    K8sEventDataID: 52060,
    CustomEventDataID: 0,
    SystemLogDataID: 0,
    CustomLogDataID: 0,
    operator_ns: 'bcs-system-staging',
    trace_data_id: 0,
    create_time: '2026-04-15 08:00:00',
    last_modify_time: '2026-04-25 14:30:00'
  },
  {
    cluster_id: 'BCS-K8S-0006',
    bcs_api_cluster_id: null,
    bk_biz_id: 6,
    project_id: 'project-staging',
    status: 'running',
    bk_env: 'development',
    K8sMetricDataID: 50070,
    CustomMetricDataID: 51070,
    K8sEventDataID: 52070,
    CustomEventDataID: 0,
    SystemLogDataID: 0,
    CustomLogDataID: 0,
    operator_ns: 'bcs-system-dev',
    trace_data_id: 0,
    create_time: '2026-04-16 08:00:00',
    last_modify_time: '2026-04-26 14:30:00'
  },
  {
    cluster_id: 'BCS-K8S-0007',
    bcs_api_cluster_id: null,
    bk_biz_id: 7,
    project_id: 'project-uat',
    status: 'running',
    bk_env: null,
    K8sMetricDataID: 50080,
    CustomMetricDataID: 51080,
    K8sEventDataID: 0,
    CustomEventDataID: 0,
    SystemLogDataID: 0,
    CustomLogDataID: 0,
    operator_ns: 'bcs-system-prod',
    trace_data_id: 0,
    create_time: '2026-04-17 08:00:00',
    last_modify_time: '2026-04-27 14:30:00'
  },
  {
    cluster_id: 'BCS-K8S-0008',
    bcs_api_cluster_id: null,
    bk_biz_id: 3,
    project_id: 'project-pre',
    status: 'abnormal',
    bk_env: null,
    K8sMetricDataID: 50090,
    CustomMetricDataID: 0,
    K8sEventDataID: 0,
    CustomEventDataID: 0,
    SystemLogDataID: 0,
    CustomLogDataID: 0,
    operator_ns: 'bcs-system-staging',
    trace_data_id: 0,
    create_time: '2026-04-18 08:00:00',
    last_modify_time: '2026-04-28 14:30:00'
  },
  {
    cluster_id: 'BCS-K8S-0009',
    bcs_api_cluster_id: null,
    bk_biz_id: 8,
    project_id: null,
    status: 'running',
    bk_env: null,
    K8sMetricDataID: 50100,
    CustomMetricDataID: 0,
    K8sEventDataID: 0,
    CustomEventDataID: 0,
    SystemLogDataID: 0,
    CustomLogDataID: 0,
    operator_ns: null,
    trace_data_id: 0,
    create_time: '2026-04-19 08:00:00',
    last_modify_time: '2026-04-29 14:30:00'
  },
  {
    cluster_id: 'BCS-K8S-0010',
    bcs_api_cluster_id: null,
    bk_biz_id: 9,
    project_id: null,
    status: 'running',
    bk_env: null,
    K8sMetricDataID: 0,
    CustomMetricDataID: 0,
    K8sEventDataID: 0,
    CustomEventDataID: 0,
    SystemLogDataID: 0,
    CustomLogDataID: 0,
    operator_ns: null,
    trace_data_id: 0,
    create_time: '2026-04-20 08:00:00',
    last_modify_time: '2026-04-30 14:30:00'
  },
  {
    cluster_id: 'BCS-K8S-0011',
    bcs_api_cluster_id: null,
    bk_biz_id: null,
    project_id: null,
    status: 'abnormal',
    bk_env: null,
    K8sMetricDataID: 0,
    CustomMetricDataID: 0,
    K8sEventDataID: 0,
    CustomEventDataID: 0,
    SystemLogDataID: 0,
    CustomLogDataID: 0,
    operator_ns: null,
    trace_data_id: 0,
    create_time: '2026-04-21 08:00:00',
    last_modify_time: '2026-05-01 14:30:00'
  },
  {
    cluster_id: 'BCS-K8S-0012',
    bcs_api_cluster_id: null,
    bk_biz_id: null,
    project_id: null,
    status: 'deleted',
    bk_env: null,
    K8sMetricDataID: 0,
    CustomMetricDataID: 0,
    K8sEventDataID: 0,
    CustomEventDataID: 0,
    SystemLogDataID: 0,
    CustomLogDataID: 0,
    operator_ns: null,
    trace_data_id: 0,
    create_time: '2026-04-22 08:00:00',
    last_modify_time: '2026-05-02 14:30:00'
  }
];

export function createMockBcsClusterDetail(clusterId: string): BcsClusterDetailResponse {
  const cluster = mockBcsClusters.find((item) => item.cluster_id === clusterId);
  if (!cluster) {
    throw new Error(`Mock BCS cluster not found: ${clusterId}`);
  }

  const dataIds = [
    cluster.K8sMetricDataID,
    cluster.CustomMetricDataID,
    cluster.K8sEventDataID,
    cluster.CustomEventDataID,
    cluster.SystemLogDataID,
    cluster.CustomLogDataID
  ].flatMap((v) => (v != null && v > 0 ? [v] : []));

  const sourceLabelMap: Record<number, string> = {
    0: 'bk_monitor',
    1: 'bk_data',
    2: 'custom'
  };
  const typeLabelMap: Record<number, string> = {
    0: 'time_series',
    1: 'event',
    2: 'log'
  };

  return {
    cluster: {
      ...cluster,
      domain_name: 'bcs-api.bk.tencent.com',
      port: 443,
      server_address_path: '/bcsapi/v4/',
      api_key_type: 'token',
      has_api_key: true,
      is_skip_ssl_verify: false
    },
    datasource_summaries: dataIds.map((id, idx) => ({
      bk_data_id: id,
      data_name: `bcs_data_${id}`,
      data_description: `BCS 集群 ${cluster.cluster_id} 的数据源 ${id}`,
      source_label: sourceLabelMap[idx % 3] || 'bk_monitor',
      type_label: typeLabelMap[idx % 3] || 'time_series',
      is_enable: id % 4 !== 0
    }))
  };
}

export function createMockDatasourceDetail(bkDataId: number): DataSourceDetailResponse {
  const fallbackDatasource = mockDatasources[0];

  if (!fallbackDatasource) {
    throw new Error('Mock datasource fixture is empty.');
  }

  const datasource =
    mockDatasources.find((item) => item.bk_data_id === bkDataId) ?? fallbackDatasource;
  const relatedResultTables = mockResultTables.filter((item) =>
    datasource.bk_data_id === 50020 ? item.table_id === '3_bklog.demo' : item.bk_biz_id === 2
  );

  return {
    datasource: {
      ...datasource,
      has_token: true,
      source_system: 'bkmonitor',
      custom_label: datasource.type_label,
      space_type_id: 'bkcc',
      etl_config: 'bk_standard_v2_time_series',
      creator: 'admin',
      last_modify_user: 'admin'
    },
    options: [
      { name: 'option_kind', value: 'demo', value_type: 'string', creator: 'admin' },
      { name: 'enable_field_black_list', value: false, value_type: 'boolean', creator: 'admin' }
    ],
    space_datasources: [
      {
        space_type_id: 'bkcc',
        space_id: datasource.space_uid?.split('__')[1] ?? '2',
        space_uid: datasource.space_uid ?? 'bkcc__2',
        bk_tenant_id: datasource.bk_tenant_id,
        bk_data_id: datasource.bk_data_id,
        from_authorization: false
      }
    ],
    data_source_result_tables: relatedResultTables.map((resultTable) => ({
      bk_data_id: datasource.bk_data_id,
      table_id: resultTable.table_id,
      table_name_zh: resultTable.table_name_zh,
      bk_biz_id: resultTable.bk_biz_id,
      data_label: resultTable.data_label,
      default_storage: resultTable.default_storage,
      is_enable: resultTable.is_enable,
      is_deleted: resultTable.is_deleted
    })),
    result_tables: relatedResultTables.map((resultTable) => ({
      bk_data_id: datasource.bk_data_id,
      table_id: resultTable.table_id,
      table_name_zh: resultTable.table_name_zh,
      bk_biz_id: resultTable.bk_biz_id,
      data_label: resultTable.data_label,
      default_storage: resultTable.default_storage,
      is_enable: resultTable.is_enable,
      is_deleted: resultTable.is_deleted
    })),
    data_id_configs: datasource.has_data_id_config
      ? [
          {
            namespace: 'bkmonitor',
            name: datasource.data_name,
            kind: 'DataId',
            created_at: null,
            updated_at: null
          }
        ]
      : [],
    kafka_cluster: datasource.kafka_cluster ?? null,
    kafka_topic_config: {
      id: datasource.mq_config_id ?? datasource.bk_data_id,
      bk_data_id: datasource.bk_data_id,
      topic: `bkmonitor_${datasource.bk_data_id}`,
      partition: datasource.bk_data_id === 50020 ? 3 : 1,
      batch_size: 500,
      flush_interval: '1s',
      consume_rate: 1000
    }
  };
}

export function createMockResultTableDetail(tableId: string): ResultTableDetailResponse {
  const fallbackResultTable = mockResultTables[0];
  const fallbackDatasource = mockDatasources[0];

  if (!fallbackResultTable || !fallbackDatasource) {
    throw new Error('Mock result table fixture is empty.');
  }

  const resultTable =
    mockResultTables.find((item) => item.table_id === tableId) ?? fallbackResultTable;
  const datasource =
    resultTable.table_id === '3_bklog.demo'
      ? (mockDatasources[1] ?? fallbackDatasource)
      : fallbackDatasource;
  const esStorages = mockEsStorages.filter((item) => item.table_id === resultTable.table_id);

  return {
    result_table: {
      ...resultTable,
      bk_biz_id_alias: `${resultTable.bk_biz_id}`,
      labels: { label: resultTable.label, data_label: resultTable.data_label },
      creator: 'admin',
      last_modify_user: 'admin'
    },
    options: [
      { name: 'segmented_query_enable', value: true, value_type: 'boolean', creator: 'admin' },
      { name: 'group_info_alias', value: { alias: resultTable.table_name_zh }, creator: 'admin' }
    ],
    datasources: [datasource],
    custom_groups: [
      {
        group_id: 1001,
        group_name: resultTable.table_name_zh,
        bk_data_id: datasource.bk_data_id,
        bk_biz_id: resultTable.bk_biz_id,
        table_id: resultTable.table_id,
        is_enable: true
      }
    ],
    es_storages: esStorages,
    es_storage: esStorages[0] ?? null,
    vm_record: resultTable.has_vm_record
      ? { result_table_id: resultTable.table_id, vm_cluster_id: 1, bk_base_data_id: 100001 }
      : null
  };
}

export function createMockEsStorageDetail(tableId: string): EsStorageDetailResponse {
  const fallbackStorage = mockEsStorages[0];
  if (!fallbackStorage) {
    throw new Error('Mock ESStorage fixture is empty.');
  }

  const storage = mockEsStorages.find((item) => item.table_id === tableId) ?? fallbackStorage;
  const resultTable = storage.result_table ?? null;
  const isVirtual = storage.table_kind === 'virtual';

  return {
    es_storage: {
      ...storage,
      index_settings: {
        number_of_shards: 1,
        number_of_replicas: 1
      },
      mapping_settings: {
        properties: {
          dtEventTimeStamp: { type: 'date' },
          message: { type: 'text' },
          trace_id: { type: 'keyword' }
        }
      },
      warm_phase_settings: {
        min_age: `${storage.warm_phase_days ?? 0}d`
      },
      long_term_storage_settings: {}
    },
    result_table: resultTable,
    storage_cluster: storage.storage_cluster ?? null,
    storage_cluster_records: [
      {
        table_id: isVirtual ? (storage.origin_table_id ?? storage.table_id) : storage.table_id,
        cluster_id: 2,
        cluster: {
          cluster_id: 2,
          cluster_name: 'bkdata-kafka',
          display_name: '历史 ES 集群',
          cluster_type: 'elasticsearch'
        },
        is_current: false,
        is_deleted: false,
        enable_time: '2026-04-01 10:00:00',
        disable_time: '2026-04-20 10:00:00',
        delete_time: null,
        creator: 'admin',
        create_time: '2026-04-01 10:00:00'
      },
      {
        table_id: isVirtual ? (storage.origin_table_id ?? storage.table_id) : storage.table_id,
        cluster_id: storage.storage_cluster_id,
        cluster: storage.storage_cluster ?? null,
        is_current: true,
        is_deleted: false,
        enable_time: '2026-04-20 10:00:00',
        disable_time: null,
        delete_time: null,
        creator: 'admin',
        create_time: '2026-04-20 10:00:00'
      }
    ],
    result_table_options: [
      { name: 'es_unique_field_list', value: ['dtEventTimeStamp', 'trace_id'], value_type: 'list' },
      { name: 'segmented_query_enable', value: true, value_type: 'boolean' }
    ],
    field_aliases: [
      {
        query_alias: 'traceId',
        field_path: 'trace_id',
        path_type: 'keyword',
        mapping_alias: { type: 'alias', path: 'trace_id' }
      },
      {
        query_alias: 'logMessage',
        field_path: 'message',
        path_type: 'text',
        mapping_alias: { type: 'alias', path: 'message' }
      }
    ],
    physical_table: isVirtual
      ? {
          table_id: storage.origin_table_id,
          exists: true,
          es_storage:
            mockEsStorages.find((item) => item.table_id === storage.origin_table_id) ?? null,
          result_table:
            mockResultTables.find((item) => item.table_id === storage.origin_table_id) ?? null
        }
      : null,
    virtual_tables: isVirtual
      ? []
      : mockEsStorages
          .filter((item) => item.origin_table_id === storage.table_id)
          .map((item) => ({
            table_id: item.table_id,
            result_table: item.result_table ?? null
          }))
  };
}

export function createMockEsRuntimeOverview(tableId: string): EsRuntimeOverviewResponse {
  const storage = mockEsStorages.find((item) => item.table_id === tableId) ?? mockEsStorages[0];
  if (!storage) {
    throw new Error('Mock ESStorage fixture is empty.');
  }

  const indexPrefix = `v2_${storage.index_set}`;

  return {
    table_id: storage.table_id,
    index_set: storage.index_set,
    index_pattern: `${indexPrefix}_*`,
    indices: [
      {
        index: `${indexPrefix}_20260425_0`,
        health: 'green',
        status: 'open',
        docs_count: 1024,
        store_size: '12mb',
        creation_date: '2026-04-25 10:00:00'
      },
      {
        index: `${indexPrefix}_20260424_0`,
        health: 'yellow',
        status: 'open',
        docs_count: 980,
        store_size: '10mb',
        creation_date: '2026-04-24 10:00:00'
      }
    ],
    aliases: [
      {
        alias: `${storage.index_set}_read`,
        indices: [`${indexPrefix}_20260425_0`, `${indexPrefix}_20260424_0`],
        is_write_index: false
      }
    ],
    mapping: {
      properties: {
        dtEventTimeStamp: { type: 'date' },
        message: { type: 'text' },
        trace_id: { type: 'keyword' },
        traceId: { type: 'alias', path: 'trace_id' }
      }
    },
    field_aliases: [
      {
        query_alias: 'traceId',
        field_path: 'trace_id',
        path_type: 'keyword',
        mapping_alias: { type: 'alias', path: 'trace_id' }
      }
    ],
    warnings:
      storage.table_kind === 'virtual'
        ? ['虚拟表 mock：运行时信息按当前 ESStorage 的 index_set 返回。']
        : []
  };
}

export function createMockEsSample(params: {
  tableId: string;
  index: string;
  timeField?: string | undefined;
}): EsSampleResponse {
  return {
    table_id: params.tableId,
    index: params.index,
    time_field: params.timeField ?? 'dtEventTimeStamp',
    took: 12,
    hit: {
      _id: 'mock-1',
      _index: params.index,
      _source: {
        dtEventTimeStamp: '2026-04-25 10:00:00',
        message: 'mock es latest log',
        trace_id: 'trace-mock-001'
      }
    },
    warnings: []
  };
}

export function createMockComponentConfig(params: {
  clusterId: number;
  namespace: string;
  kind: string;
  name: string;
}): ComponentConfigResponse {
  void params;
  return {
    component_config: {
      sources: [{ type: 'kafka', brokers: ['localhost:9092'], topic: 'input-topic' }],
      sinks: [{ type: 'elasticsearch', cluster: 'es-cluster-1', index_pattern: 'logs-*' }],
      transforms: [{ type: 'filter', field: 'status', condition: 'exists' }],
      status: { phase: 'Ok', message: 'mock component config is healthy' }
    }
  };
}

export function createMockClusterInfoDetail(clusterId: number): ClusterInfoDetailResponse {
  const fallbackCluster = mockClusterInfos[0];
  if (!fallbackCluster) {
    throw new Error('Mock cluster fixture is empty.');
  }
  const cluster = mockClusterInfos.find((item) => item.cluster_id === clusterId) ?? fallbackCluster;

  return {
    cluster_info: cluster,
    cluster_configs: [
      {
        namespace: 'default',
        kind: cluster.cluster_type === 'elasticsearch' ? 'ElasticsearchCluster' : 'KafkaCluster',
        name: cluster.cluster_name,
        origin_config: {
          cluster_id: cluster.cluster_id,
          cluster_name: cluster.cluster_name
        },
        component_config: {
          status: { phase: 'Ok', message: 'mock ready' }
        },
        created_at: cluster.create_time,
        updated_at: cluster.last_modify_time
      }
    ],
    related_result_tables: cluster.cluster_type === 'elasticsearch' ? mockEsStorages.length : 0,
    related_datasources: cluster.associated_datasources
  };
}

export function createMockFieldList(
  tableId: string,
  page: number,
  pageSize: number,
  fieldName?: string
): ResultTableFieldListResponse {
  const allFields = Array.from({ length: 128 }, (_, index) => {
    const position = index + 1;

    return {
      field_name: position === 1 ? 'time' : `metric_${position}`,
      field_type: position === 1 ? 'timestamp' : 'double',
      tag: position % 5 === 0 ? 'dimension' : 'metric',
      description: `${tableId} 字段 ${position}`,
      unit: position % 5 === 0 ? null : 'none',
      is_config_by_user: position % 3 === 0,
      alias_name: `字段 ${position}`,
      is_disabled: false,
      last_modify_time: '2026-04-23 12:00:00',
      option_count: position % 4 === 0 ? 1 : 0,
      options:
        position % 4 === 0
          ? [{ name: 'es_field_type', value: 'keyword', value_type: 'string' }]
          : []
    };
  }).filter((field) => (fieldName ? field.field_name.includes(fieldName) : true));
  const start = (page - 1) * pageSize;

  return {
    items: allFields.slice(start, start + pageSize),
    page,
    page_size: pageSize,
    total: allFields.length
  };
}

export function createMockQueryRoute(params: Record<string, unknown>): QueryRouteResponse {
  const inputTableIds = readStringArray(params.table_ids);
  const inputDataLabels = readStringArray(params.data_labels);
  const inputFieldNames = readStringArray(params.field_names);
  const tableIds =
    inputTableIds.length > 0
      ? inputTableIds
      : ['2_bkmonitor_time_series.__default__', '3_bklog.demo', '2_missing.demo'];
  const dataLabels =
    inputDataLabels.length > 0 ? inputDataLabels : ['custom_metric_demo', 'bkdata_link_demo'];
  const spaceUid = typeof params.space_uid === 'string' ? params.space_uid : 'bkcc__2';
  const fields = createMockQueryRouteFields(tableIds[0] ?? '2_bkmonitor_time_series.__default__');
  const inputTableIdSet = new Set(inputTableIds);

  const resultTableDetails = tableIds.map((tableId) => {
    const exists = tableId !== '2_missing.demo';
    const isLog = tableId.includes('bklog');
    const detailFields = exists && !isLog ? fields : [];
    const fieldNameSet = new Set(detailFields.map((field) => field.field_name));

    return {
      table_id: tableId,
      exists,
      storage_type: isLog ? 'elasticsearch' : 'influxdb',
      storage_id: isLog ? 'default-es' : 'default-influxdb',
      db: isLog ? '3_bklog' : 'bkmonitor_custom_metric',
      measurement: isLog ? 'demo' : '__default__',
      field_count: detailFields.length,
      matched_field_names: inputFieldNames.filter((fieldName) => fieldNameSet.has(fieldName)),
      missing_field_names: exists
        ? inputFieldNames.filter((fieldName) => !fieldNameSet.has(fieldName))
        : inputFieldNames,
      fields: detailFields,
      detail: exists
        ? {
            table_id: tableId,
            data_label: isLog ? 'bkdata_link_demo' : 'custom_metric_demo',
            storage_type: isLog ? 'elasticsearch' : 'influxdb',
            db: isLog ? '3_bklog' : 'bkmonitor_custom_metric',
            measurement: isLog ? 'demo' : '__default__',
            fields: detailFields
          }
        : null
    };
  });

  const spaceRoutes = tableIds
    .filter((tableId) => tableId !== '2_missing.demo')
    .map((tableId, index) => ({
      table_id: tableId,
      filters: [
        {
          conditions: [
            { field: 'dimensions.bk_biz_id', operator: '=', value: index === 0 ? 2 : 3 },
            {
              field: 'source_type',
              operator: '=',
              value: tableId.includes('bklog') ? 'log' : 'metric'
            }
          ],
          raw: {
            'dimensions.bk_biz_id': index === 0 ? 2 : 3,
            source_type: tableId.includes('bklog') ? 'log' : 'metric'
          }
        },
        {
          conditions: [{ field: 'dimensions.cluster_id', operator: '=', value: 'BCS-K8S-00000' }],
          raw: { 'dimensions.cluster_id': 'BCS-K8S-00000' }
        }
      ],
      in_input_table_ids: inputTableIdSet.size === 0 || inputTableIdSet.has(tableId),
      in_any_data_label: true,
      has_detail: tableId !== '2_missing.demo',
      raw: {
        space_uid: spaceUid,
        table_id: tableId
      }
    }));

  const dataLabelRoutes = dataLabels.map((dataLabel) => {
    const routedTableIds = dataLabel.includes('log')
      ? ['3_bklog.demo']
      : ['2_bkmonitor_time_series.__default__', '2_missing.demo'];

    return {
      data_label: dataLabel,
      exists: routedTableIds.length > 0,
      table_ids: routedTableIds.map((tableId) => ({
        table_id: tableId,
        in_space: spaceRoutes.some((route) => route.table_id === tableId),
        has_detail: resultTableDetails.some(
          (detail) => detail.table_id === tableId && detail.exists
        ),
        in_input_table_ids: inputTableIdSet.has(tableId)
      })),
      raw: {
        data_label: dataLabel,
        table_ids: routedTableIds
      }
    };
  });

  return {
    space_uid: spaceUid,
    inputs: {
      spaceUid,
      tableIds,
      dataLabels,
      fieldNames: inputFieldNames
    },
    space_routes: spaceRoutes,
    data_label_routes: dataLabelRoutes,
    result_table_details: resultTableDetails,
    diagnostics: [
      {
        id: 'space-ok',
        status: 'ok',
        label: 'space 路由包含 table_id',
        target: tableIds[0] ?? '-',
        message: `${tableIds[0] ?? '-'} OK`
      },
      {
        id: 'detail-missing',
        status: 'missing',
        label: 'result_table_detail 存在',
        target: '2_missing.demo',
        message: '2_missing.demo Missing'
      },
      {
        id: 'field-missing',
        status: inputFieldNames.includes('missing_field') ? 'missing' : 'ok',
        label: '字段检查',
        target: 'missing_field',
        message: inputFieldNames.includes('missing_field')
          ? 'missing_field 不存在于 result_table_detail.fields'
          : '字段检查 OK'
      }
    ],
    warnings: ['mock 数据覆盖 space/data_label/detail/filter_groups/fields/diagnostics/refresh。']
  };
}

function createMockQueryRouteFields(tableId: string) {
  return Array.from({ length: 128 }, (_, index) => {
    const position = index + 1;
    const fieldName = position === 1 ? 'time' : `metric_${position}`;

    return {
      field_name: fieldName,
      field_type: position === 1 ? 'timestamp' : 'double',
      tag: position % 5 === 0 ? 'dimension' : 'metric',
      description: `${tableId} 字段 ${position}`,
      alias_name: position === 1 ? '时间' : `指标 ${position}`,
      raw: {
        field_name: fieldName,
        type: position === 1 ? 'timestamp' : 'double'
      }
    };
  });
}

function readStringArray(value: unknown): string[] {
  return Array.isArray(value)
    ? value.flatMap((item) => (typeof item === 'string' ? [item] : []))
    : [];
}
