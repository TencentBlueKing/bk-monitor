export const BCS_STATUS_OPTIONS = [
  { label: '运行中', value: 'running' },
  { label: '已删除', value: 'deleted' },
  { label: '初始化失败', value: 'init_failed' }
];

export const BCS_STATUS_TONE: Record<
  string,
  'default' | 'success' | 'danger' | 'warning' | 'muted'
> = {
  running: 'success',
  deleted: 'danger',
  init_failed: 'warning'
};
