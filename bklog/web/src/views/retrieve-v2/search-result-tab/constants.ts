import { t } from '@/hooks/use-locale';

// tab类型常量定义
export const TAB_TYPES = {
  LOG_LEVEL: t('日志分级展示'),
  LOG_KEYWORD: t('日志关键词设置'),
  LOG_METRIC: t('日志转指标'),
} as const;

export type TabType = (typeof TAB_TYPES)[keyof typeof TAB_TYPES];
