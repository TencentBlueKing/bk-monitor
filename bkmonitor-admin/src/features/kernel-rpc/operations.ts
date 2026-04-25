export const operationToFuncName = {
  'tenant.list': 'admin.tenant.list',
  'datasource.list': 'admin.datasource.list',
  'datasource.detail': 'admin.datasource.detail',
  'datasource.kafka_sample': 'admin.datasource.kafka_sample',
  'datasource.data_id_config.component_config': 'admin.datasource.data_id_config.component_config',
  'result_table.list': 'admin.result_table.list',
  'result_table.detail': 'admin.result_table.detail',
  'result_table.field_list': 'admin.result_table.field_list',
  'result_table.field_options': 'admin.result_table.field_options',
  'es_storage.list': 'admin.es_storage.list',
  'es_storage.detail': 'admin.es_storage.detail',
  'es_storage.runtime_overview': 'admin.es_storage.runtime_overview',
  'es_storage.sample': 'admin.es_storage.sample',
  'cluster_info.list': 'admin.cluster_info.list',
  'cluster_info.detail': 'admin.cluster_info.detail',
  'cluster_info.component_config': 'admin.cluster_info.component_config',
  'bcs_cluster.list': 'admin.bcs_cluster.list',
  'bcs_cluster.detail': 'admin.bcs_cluster.detail',
  'query_route.query': 'admin.query_route.query',
  'query_route.refresh': 'admin.query_route.refresh'
} as const;

export type AdminOperation = keyof typeof operationToFuncName;

export function getFuncName(operation: AdminOperation): string {
  return operationToFuncName[operation];
}
