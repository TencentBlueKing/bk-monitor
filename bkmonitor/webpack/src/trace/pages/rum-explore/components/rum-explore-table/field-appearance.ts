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
import { h } from 'vue';

import {
  RUM_HTTP_STATUS_CODE_MAP,
  RUM_STATUS_CODE_MAP,
  RumHttpStatusCodeGroupEnum,
  SPAN_KIND_MAPS,
  SPAN_TYPE_META,
} from '../../constants';

import type { FieldAppearance, IRumField, SpanKindPrefixIcon } from '../../typings';
import type { CellIconConfig } from './components/cell-icon/cell-icon';

/**
 * @description 按接口阈值顺序匹配数值评级，未命中时取最后一档。
 * @param field 包含评级阈值的字段元信息
 * @param value 字段原始值
 * @returns 评级样式类，数组、非有限数值或无有效评级时返回空串
 */
export const getRatingClass = (field: IRumField | undefined, value: unknown) => {
  const thresholds = field?.rating_config;
  const number = Number(value);
  if (!thresholds?.length || Array.isArray(value) || !Number.isFinite(number)) return '';
  const rating = (thresholds.find(item => item.value === undefined || number <= item.value) ?? thresholds.at(-1))
    ?.rating;
  if (!['good', 'needs_improvement', 'poor'].includes(rating)) return '';
  return `rum-rating-value is-${rating.replace('_', '-')}`;
};

/**
 * @description 将旧字库类名拆成图标名和样式类，字库基础类由 CellIcon 提供。
 * @param fontClasses 包含图标名和样式类的字库类名
 * @param className 调用方补充的图标样式类
 * @returns CellIcon 配置，无图标名时返回 undefined
 */
const toFontIconConfig = (fontClasses: string, className: string): CellIconConfig | undefined => {
  const [icon, ...styleClasses] = fontClasses
    .trim()
    .split(/\s+/)
    .filter(name => name !== 'icon-monitor');
  return icon ? { icon, className: [className, ...styleClasses].join(' ') } : undefined;
};

/**
 * @description 判断 Trace 的 kind 图标是否可直接用于 RUM 字段。
 * @param icon Trace 的 kind 图标类名或渲染回调
 * @returns 回调无需表格上下文时返回 true
 */
const isContextFreeKindIcon = (
  icon: SpanKindPrefixIcon | undefined
): icon is () => ReturnType<Exclude<SpanKindPrefixIcon, string>> => typeof icon === 'function' && icon.length === 0;

/**
 * @description 按 HTTP 状态码百位分组生成颜色样式。
 * @param value 原始 HTTP 状态码
 * @param badge 是否用作复合列标签，决定使用标签色变量还是前景与背景色
 * @returns 对应分组的展示样式，未配置的分组返回空对象
 */
export function httpStatusAppearance(value: unknown, badge: boolean): FieldAppearance {
  const group = Math.floor(Number(value) / 100);
  const config = RUM_HTTP_STATUS_CODE_MAP[group];
  if (!config) return {};
  const tint = group === RumHttpStatusCodeGroupEnum.SUCCESS ? '#23ad89' : config.tagBgColor;
  return {
    style: badge ? { '--rum-badge-tint': tint } : { color: config.tagColor, backgroundColor: config.tagBgColor },
  };
}

/**
 * @description 复用 Trace 的 kind 枚举别名及图标。
 * @param value 原始 kind 值
 * @returns 适配 CellIcon 的图标和备用文案
 */
export function kindAppearance(value: unknown): FieldAppearance {
  const meta = SPAN_KIND_MAPS[Number(value)];
  const icon = meta?.prefixIcon;
  if (typeof icon === 'string') return { text: meta.alias, icon: toFontIconConfig(icon, 'prefix-icon') };
  return { text: meta?.alias, icon: isContextFreeKindIcon(icon) ? { icon } : undefined };
}

/**
 * @description 读取 Span 类型的展示元数据，优先使用图片图标，其次使用字库图标。
 * @param value 原始 Span 类型
 * @returns 类型对应的图标和备用文案
 */
export function spanTypeAppearance(value: unknown): FieldAppearance {
  const { icon: source, fontIcon, label } = SPAN_TYPE_META[String(value)] ?? {};
  if (source) return { text: label, icon: { icon: () => h('img', { class: 'span-type-icon', alt: '', src: source }) } };
  return {
    text: label,
    icon: fontIcon ? toFontIconConfig(fontIcon, 'span-type-font-icon') : undefined,
  };
}

/**
 * @description 将 Span 状态码映射到备用文案和标签配色。
 * @param value 原始 Span 状态码
 * @param badge 是否用作复合列标签，决定使用标签色变量还是前景与背景色
 * @returns 状态码展示配置，未知状态码返回空对象
 */
export function statusAppearance(value: unknown, badge: boolean): FieldAppearance {
  const config = RUM_STATUS_CODE_MAP[Number(value)];
  if (!config) return {};
  return {
    text: config.alias,
    style: badge
      ? { '--rum-badge-tint': config.tagColor }
      : { color: config.tagColor, backgroundColor: config.tagBgColor },
  };
}
