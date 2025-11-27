import { t } from '@/hooks/use-locale';

// tab类型常量定义
export const TAB_TYPES = {
  KEYWORD: t('日志关键词设置'),
  METRIC: t('日志转指标'),
} as const;

export type TabType = (typeof TAB_TYPES)[keyof typeof TAB_TYPES];
