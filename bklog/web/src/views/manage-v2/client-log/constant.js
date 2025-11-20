import { t } from '@/hooks/use-locale';

// 任务阶段选项
const TASK_STAGE_OPTIONS = [
  { value: 1, label: t('登录前') },
  { value: 4, label: t('登录后') },
];

// 客户端类型选项
const CLIENT_TYPE_OPTIONS = [
  { value: '', label: t('默认') },
  { value: '安装', label: t('安装') },
  { value: 'iOS', label: 'iOS' },
  { value: 'macOS', label: 'macOS' },
  { value: 'Windows', label: 'Windows' },
  { value: 'Harmony', label: 'Harmony' },
];

// 触发频率选项
const TRIGGER_FREQUENCY_OPTIONS = [
  { value: 'single', label: t('单次触发') },
  { value: 'sustain', label: t('持续触发') },
];

// 持续触发时长选项
const SUSTAIN_TIME_OPTIONS = [
  { value: 3600, label: t('1小时') }, // 1小时 = 3600秒
  { value: 10800, label: t('{n}小时', { n: 3 }) }, // 3小时 = 10800秒
  { value: 43200, label: t('{n}小时', { n: 12 }) }, // 12小时 = 43200秒
  { value: 86400, label: t('1天') }, // 1天 = 86400秒
  { value: 259200, label: t('{n}天', { n: 3 }) }, // 3天 = 259200秒
  { value: 604800, label: t('{n}天', { n: 7 }) }, // 7天 = 604800秒
];

export { TASK_STAGE_OPTIONS, CLIENT_TYPE_OPTIONS, TRIGGER_FREQUENCY_OPTIONS, SUSTAIN_TIME_OPTIONS };
