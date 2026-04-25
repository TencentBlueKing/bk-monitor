export const SCHEMA_TYPE_OPTIONS = [
  { label: '无固定字段', value: 'free' },
  { label: '动态字段', value: 'dynamic' },
  { label: '固定字段', value: 'fixed' }
];

export const DEFAULT_STORAGE_OPTIONS = [
  { label: 'influxDB', value: 'influxdb' },
  { label: 'kafka', value: 'kafka' },
  { label: 'redis', value: 'redis' },
  { label: 'elasticsearch', value: 'elasticsearch' },
  { label: 'argus', value: 'argus' },
  { label: 'victoria_metrics', value: 'victoria_metrics' },
  { label: 'doris', value: 'doris' },
  { label: 'bkdata', value: 'bkdata' }
];

// 以下为常见参考值，实际可选值来自 Label DB 表（label_type='result_table_label'），可能随时间变化
export const LABEL_COMMON = [
  'applications',
  'uptimecheck',
  'application_check',
  'apm',
  'services',
  'service_module',
  'component',
  'hosts',
  'host_process',
  'os',
  'host_device',
  'kubernetes',
  'data_center',
  'hardware_device',
  'others',
  'other_rt'
] as const;
