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
 * documentation files (the "Software"), to deal in the Software without restriction, including without limitation the
 * rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
 * permit persons to whom the Software is furnished to do so, subject to the following conditions:
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

import { formatDuration, formatTraceTableDate } from '../../../components/trace-view/utils/date';
import { TABLE_DEFAULT_CONFIG } from '../../trace-explore/components/trace-explore-table/constants';
import { RumFieldDisplayEnum } from '../constants';
import { formatUnitValue } from './unit-formatter';

import type { IRumField } from '../typings';

/** 数组项空值统一展示的占位符，与主表空态一致 */
export const ARRAY_ITEM_EMPTY_PLACEHOLDER = TABLE_DEFAULT_CONFIG.tableConfig.emptyPlaceholder;

/** 数组项格式化方法：仅处理非空值，空值由 formatArrayItem 统一兜底 */
export type ArrayItemFormatter = (value: unknown) => string;

/**
 * @description 数组项取值：空洞项统一展示为空占位符，避免出现 null / undefined 字面量
 * @param {unknown} value 数组项原始值
 * @param {ArrayItemFormatter} formatter 按字段语义推导出的格式化方法
 * @returns {string} 数组项展示文本
 */
export const formatArrayItem = (value: unknown, formatter: ArrayItemFormatter): string => {
  if (value === null || value === undefined || value === '') return ARRAY_ITEM_EMPTY_PLACEHOLDER;
  return formatter(value);
};

/**
 * @description 优先显示接口枚举别名，再按展示类型和单位格式化，最后回退到原值。
 * @param value 原始字段值
 * @param field 接口下发的字段元信息
 * @param vitalMetric 当前行的指标名，用于区分 CLS 和耗时指标
 * @param fallbackText 字段组件提供的特殊文案
 * @returns 列表或数组抽屉使用的显示文本
 */
export const formatFieldValue = (
  value: unknown,
  field?: IRumField,
  vitalMetric?: unknown,
  fallbackText?: string
): string => {
  const alias = field?.option_values?.find(item => `${item.value}` === `${value}`)?.alias;
  if (alias) return alias;

  const unit = field?.field_unit;
  if (unit === 'vital') {
    const number = Number(value);
    return String(vitalMetric).toLowerCase() === 'cls' || !Number.isFinite(number)
      ? String(value)
      : formatDuration(number, '', 2, 'ms');
  }
  switch (field?.field_display_type) {
    case RumFieldDisplayEnum.DATETIME:
      return formatTraceTableDate(value as number | string);
    case RumFieldDisplayEnum.DURATION: {
      const number = Number(value);
      if (!Number.isFinite(number)) return String(value);
      if (!unit || unit === 'ms' || unit === 'us') return formatDuration(number, '', 2, unit || 'us');
      return formatUnitValue(number, unit);
    }
    default:
      if (unit) return formatUnitValue(value, unit);
      return fallbackText ?? (typeof value === 'object' ? JSON.stringify(value) : String(value));
  }
};
/**
 * @description 数组项格式化器：按字段语义推导逐项格式化方法，使 events.timestamp 的每一项都是
 *              格式化后的日期时间、带单位字段的每一项都带单位，避免数组样式下退化成原始数值。
 *              主表单元格与数组列表抽屉共用同一实现，避免两处展示漂移。
 * @param {IRumField | undefined} field 字段元数据
 * @returns {ArrayItemFormatter} 单项格式化方法
 */
export const resolveArrayItemFormatter =
  (field?: IRumField): ArrayItemFormatter =>
  value =>
    formatFieldValue(value, field);
