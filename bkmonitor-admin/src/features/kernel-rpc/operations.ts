export const operationToFuncName = {
  'tenant.list': 'admin.tenant.list',
  'datasource.list': 'admin.datasource.list',
  'datasource.detail': 'admin.datasource.detail',
  'result_table.list': 'admin.result_table.list',
  'result_table.detail': 'admin.result_table.detail',
  'result_table.field_list': 'admin.result_table.field_list',
  'result_table.field_options': 'admin.result_table.field_options'
} as const;

export type AdminOperation = keyof typeof operationToFuncName;

export function getFuncName(operation: AdminOperation): string {
  return operationToFuncName[operation];
}
