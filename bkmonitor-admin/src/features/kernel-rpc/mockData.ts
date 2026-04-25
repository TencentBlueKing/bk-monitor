import type { DataSourceDetailResponse, DataSourceListResponse } from '../datasource/schemas';
import type { ClusterInfoDetailResponse, ClusterInfoListResponse } from '../cluster-info/schemas';
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
    data_id_config: datasource.has_data_id_config
      ? { namespace: 'bkmonitor', name: datasource.data_name, kind: 'bkdata' }
      : null,
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
          es_storage: mockEsStorages.find((item) => item.table_id === storage.origin_table_id) ?? null,
          result_table: mockResultTables.find((item) => item.table_id === storage.origin_table_id) ?? null
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
      option_count: position % 4 === 0 ? 1 : 0
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
