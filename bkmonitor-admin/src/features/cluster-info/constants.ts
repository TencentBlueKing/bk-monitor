export const CLUSTER_TYPE_OPTIONS = [
  { label: 'influxDB', value: 'influxdb' },
  { label: 'kafka', value: 'kafka' },
  { label: 'redis', value: 'redis' },
  { label: 'elasticsearch', value: 'elasticsearch' },
  { label: 'argus', value: 'argus' },
  { label: 'victoria_metrics', value: 'victoria_metrics' },
  { label: 'doris', value: 'doris' },
  { label: 'bkdata', value: 'bkdata' }
];

export const CLUSTER_TYPE_TONE: Record<
  string,
  'default' | 'success' | 'danger' | 'warning' | 'muted'
> = {
  kafka: 'default',
  elasticsearch: 'success',
  influxdb: 'warning',
  redis: 'danger',
  victoria_metrics: 'default',
  doris: 'default',
  argus: 'muted',
  bkdata: 'muted'
};
