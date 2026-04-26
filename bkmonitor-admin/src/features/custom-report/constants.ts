import { Activity, BellDot, ScrollText } from 'lucide-react';

export const CUSTOM_REPORT_TYPE_TABS = [
  { reportType: 'custom_metric', label: '指标', icon: Activity },
  { reportType: 'custom_event', label: '事件', icon: BellDot },
  { reportType: 'custom_log', label: '日志', icon: ScrollText }
] as const;

export const CUSTOM_REPORT_CREATED_FROM_OPTIONS = [
  { label: 'monitor_web', value: 'monitor_web' },
  { label: 'metadata', value: 'metadata' },
  { label: 'apm', value: 'apm' },
  { label: 'bkdata', value: 'bkdata' }
] as const;
