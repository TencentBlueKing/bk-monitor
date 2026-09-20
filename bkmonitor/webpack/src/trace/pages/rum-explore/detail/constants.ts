/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台 (BlueKing PaaS):
 *
 * ---------------------------------------------------
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
 * documentation files (the "Software"), to deal in the Software without restriction, including without limitation
 * the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
 * to permit persons to whom the Software is furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all copies or substantial portions of
 * the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
 * THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
 * CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
 * IN THE SOFTWARE.
 */
import { RumCardToneEnum, RumRatingEnum } from './typings';

import type { RumCardToneType } from './typings';

/** 后端计算字段的前缀，此类字段的别名与格式化值由后端直接给出 */
export const DISPLAY_FIELD_PREFIX = 'display.';

/**
 * 公共信息项的展示名覆盖。
 * view_config 里的 field_alias 面向检索列（如「页面 URL 模板」），详情头部需要更短的说明文案，
 * 故按设计稿在此覆盖；未登记的字段仍走 field_alias -> field_name 的兜底链路。
 */
export const OVERVIEW_ITEM_LABEL_MAP: Record<string, string> = {
  app_name: window.i18n.t('应用'),
  start_time: window.i18n.t('开始'),
  end_time: window.i18n.t('结束'),
  'attributes.view.url_template': window.i18n.t('视图'),
  'attributes.session.id': window.i18n.t('会话'),
  'attributes.view.id': window.i18n.t('View 详情'),
  'attributes.user.id': window.i18n.t('用户'),
  'resource.deployment.environment.name': window.i18n.t('环境'),
};

/** 以蓝色可点击样式展示的公共信息项 */
export const OVERVIEW_LINK_FIELDS = new Set([
  'attributes.view.url_template',
  'attributes.session.id',
  'attributes.view.id',
]);

/** 以微秒时间戳存储、需按日期时间展示的公共信息项 */
export const OVERVIEW_DATETIME_FIELDS = new Set(['start_time', 'end_time', 'attributes.view.started_at']);

/** 耗时类徽标的字段，统一渲染为灰蓝底 + 计时器图标 */
export const DURATION_BADGE_FIELDS = new Set(['elapsed_time', 'attributes.vital.value', 'display.view.duration']);

/** 类型类徽标的字段，统一渲染为主蓝底 */
export const TYPE_BADGE_FIELDS = new Set([
  'attributes.resource.type',
  'attributes.action.type',
  'attributes.long_task.entry_type',
]);

/** 徽标配色 */
export const BADGE_COLOR = {
  /** 耗时徽标 */
  duration: { bgColor: '#8F9FBD', color: '#FFFFFF' },
  /** 类型徽标 */
  type: { bgColor: '#3A84FF', color: '#FFFFFF' },
  /** 未命中任何规则时的兜底 */
  default: { bgColor: '#8F9FBD', color: '#FFFFFF' },
} as const;

/** attributes.outcome.type 徽标配色，与表格列的状态语义保持一致 */
export const OUTCOME_BADGE_COLOR: Record<string, { bgColor: string; color: string }> = {
  success: { bgColor: '#21A380', color: '#FFFFFF' },
  warning: { bgColor: '#FF9C01', color: '#FFFFFF' },
  error: { bgColor: '#EA3636', color: '#FFFFFF' },
  timeout: { bgColor: '#FF9C01', color: '#FFFFFF' },
  abort: { bgColor: '#8F9FBD', color: '#FFFFFF' },
};

/** Web Vitals 评级的展示配置 */
export const RATING_META: Record<string, { alias: string; badgeBgColor: string; barColor: string; color: string }> = {
  [RumRatingEnum.GOOD]: {
    alias: window.i18n.t('良好'),
    color: '#21A380',
    barColor: '#21A380',
    badgeBgColor: '#E5F6F0',
  },
  [RumRatingEnum.NEEDS_IMPROVEMENT]: {
    alias: window.i18n.t('需改进'),
    color: '#E38B02',
    barColor: '#F8B64F',
    badgeBgColor: '#FDF4E8',
  },
  [RumRatingEnum.POOR]: {
    alias: window.i18n.t('差'),
    color: '#EA3636',
    barColor: '#EA3636',
    badgeBgColor: '#FDE7E7',
  },
};

/** 评级未命中枚举时的兜底配置 */
export const RATING_FALLBACK_META = {
  alias: '',
  color: '#4D4F56',
  barColor: '#C1CDE5',
  badgeBgColor: '#F0F1F5',
};

/**
 * Web Vitals 指标的展示元数据。
 * unit 为空表示无量纲分数（CLS），评级刻度与指标值都不拼单位。
 */
export const VITAL_METRIC_META: Record<string, { label: string; unit: string }> = {
  lcp: { label: window.i18n.t('最大内容绘制（Largest Contentful Paint，LCP）') as string, unit: 'ms' },
  fcp: { label: window.i18n.t('首次内容绘制（First Contentful Paint，FCP）') as string, unit: 'ms' },
  inp: { label: window.i18n.t('下次绘制交互（Interaction to Next Paint，INP）') as string, unit: 'ms' },
  ttfb: { label: window.i18n.t('首字节时间（Time to First Byte，TTFB）') as string, unit: 'ms' },
  cls: { label: window.i18n.t('累积布局偏移（Cumulative Layout Shift，CLS）') as string, unit: 'ms' },
};

/** 统计卡片主值的语义配色 */
export const CARD_TONE_COLOR: Record<RumCardToneType, string> = {
  [RumCardToneEnum.DEFAULT]: '#313238',
  [RumCardToneEnum.SUCCESS]: '#21A380',
  [RumCardToneEnum.WARNING]: '#F59500',
  [RumCardToneEnum.DANGER]: '#EA3636',
  [RumCardToneEnum.LINK]: '#3A84FF',
};

/**
 * 瀑布图各阶段的色值。
 * 阶段集合由后端 phases[].key 决定，未登记的阶段按声明顺序取 WATERFALL_FALLBACK_COLORS 轮转。
 */
export const WATERFALL_PHASE_COLOR: Record<string, string> = {
  prepare: '#51CFFD',
  dns: '#85CDFF',
  connect: '#7BC8A4',
  tls: '#A3B8F0',
  first_byte: '#FFC455',
  download: '#FF7A55',
  dom_processing: '#FFB980',
  resource_load: '#8D98B3',
  page_stable: '#C1CDE5',
};

export const WATERFALL_FALLBACK_COLORS = ['#51CFFD', '#FFC455', '#FF7A55', '#7BC8A4', '#A3B8F0', '#8D98B3'];

/**
 * 瀑布图中被合并成一条说明线的连续阶段。
 * 命中时这些阶段不单独占行，改为在上一行下方渲染「连接复用：DNS、TCP、TLS」的说明。
 */
export const WATERFALL_MERGED_PHASES: Record<string, string> = {
  dns: 'DNS',
  connect: 'TCP',
  tls: 'TLS',
};

/** 瀑布图中代表 TTFB 时间点的标记 key，缺失时不推导 TTFB 分解说明 */
export const WATERFALL_TTFB_MARKER_KEY = 'TTFB';

/** 区块标识，与接口 sections[].key 对齐 */
export const SectionKeyEnum = {
  /** 关键信息 */
  KEY_INFO: 'key_info',
  /** 资源详情 */
  RESOURCE_INFO: 'resource_info',
  /** 请求时序 */
  LOADING_TIMING: 'loading_timing',
  /** 指标评级 */
  VITAL_RATING: 'vital_rating',
  /** 网页指标 */
  WEB_VITALS: 'web_vitals',
  /** 影响面统计（前端扩展区块） */
  IMPACT: 'impact',
  /** 版本关联（前端扩展区块） */
  VERSION: 'version',
} as const;

/** 区块标题，key 未登记时不渲染标题行 */
export const SECTION_TITLE_MAP: Record<string, string> = {
  [SectionKeyEnum.KEY_INFO]: window.i18n.t('关键信息'),
  [SectionKeyEnum.RESOURCE_INFO]: window.i18n.t('资源详情'),
  [SectionKeyEnum.LOADING_TIMING]: window.i18n.t('请求时序'),
  [SectionKeyEnum.WEB_VITALS]: window.i18n.t('网页指标'),
  [SectionKeyEnum.IMPACT]: window.i18n.t('影响面统计'),
  [SectionKeyEnum.VERSION]: window.i18n.t('版本关联'),
};

/** 一行最多放几张统计卡片，超出换行 */
export const CARDS_PER_ROW = 5;

/**
 * 统计卡片分组的标题映射，key 为 `${spanType}.${sectionKey}`，未命中回退 `${sectionKey}`。
 * 登记的区块按分组形态渲染（组标题栏 + 组内卡片平铺，外层不再渲染区块标题行），
 * 未登记的保持原有的一字排开形态。
 */
export const CARD_GROUP_TITLE_MAP: Record<string, string> = {
  [`view.${SectionKeyEnum.KEY_INFO}`]: window.i18n.t('核心结果'),
  [`view.${SectionKeyEnum.WEB_VITALS}`]: window.i18n.t('Web Vitals'),
};

/** origin_data 中不参与 Span 折叠块展示的嵌套字段（各自已有独立折叠块） */
export const ORIGIN_NESTED_KEYS = new Set(['attributes', 'resource', 'events', 'links']);
