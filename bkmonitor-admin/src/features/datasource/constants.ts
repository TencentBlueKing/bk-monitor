// 线上实际数据（由 DataSource.objects.values().annotate(count=Count(...)) 提取）
// 用户可自定义输入，以下为常见候选值
export const SOURCE_LABEL_COMMON = ['bk_monitor', 'custom', 'others'] as const;

export const TYPE_LABEL_COMMON = ['time_series', 'event', 'log', 'others', 'bk_event'] as const;

export const CREATED_FROM_OPTIONS = [
  { label: 'V3 (GSE)', value: 'bkgse' },
  { label: 'V4 (计算平台)', value: 'bkdata' }
];
