export const operationToFuncName = {
  'tenant.list': 'admin.tenant.list',
  'datasource.list': 'admin.datasource.list',
  'datasource.detail': 'admin.datasource.detail',
  'datasource.kafka_sample': 'admin.datasource.kafka_sample',
  'result_table.list': 'admin.result_table.list',
  'result_table.detail': 'admin.result_table.detail',
  'result_table.field_list': 'admin.result_table.field_list',
  'result_table.field_options': 'admin.result_table.field_options',
  'cluster_info.list': 'admin.cluster_info.list',
  'cluster_info.detail': 'admin.cluster_info.detail',
  'bcs_cluster.list': 'admin.bcs_cluster.list',
  'bcs_cluster.detail': 'admin.bcs_cluster.detail'
} as const;

export type AdminOperation = keyof typeof operationToFuncName;

export function getFuncName(operation: AdminOperation): string {
  return operationToFuncName[operation];
}
