export const BCS_STATUS_OPTIONS = [
  { label: 'RUNNING', value: 'RUNNING' },
  { label: 'running', value: 'running' },
  { label: 'DELETED', value: 'DELETED' },
  { label: 'deleted', value: 'deleted' },
  { label: 'init_failed', value: 'init_failed' }
];

export const BCS_STATUS_TONE: Record<
  string,
  'default' | 'success' | 'danger' | 'warning' | 'muted'
> = {
  running: 'success',
  RUNNING: 'success',
  deleted: 'danger',
  DELETED: 'danger',
  init_failed: 'warning'
};
