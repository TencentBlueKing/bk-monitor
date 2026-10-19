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
export function formatArrayItem(value: unknown, formatter: ArrayItemFormatter): string {
  if (value === null || value === undefined || value === '') return ARRAY_ITEM_EMPTY_PLACEHOLDER;
  return formatter(value);
}

/**
 * @description 数组项格式化器：按字段语义推导逐项格式化方法，使 events.timestamp 的每一项都是
 *              格式化后的日期时间、带单位字段的每一项都带单位，避免数组样式下退化成原始数值。
 *              主表单元格与数组列表抽屉共用同一实现，避免两处展示漂移。
 * @param {IRumField | undefined} field 字段元数据
 * @returns {ArrayItemFormatter} 单项格式化方法
 */
export function resolveArrayItemFormatter(field?: IRumField): ArrayItemFormatter {
  const unit = field?.field_unit;
  switch (field?.field_display_type) {
    case RumFieldDisplayEnum.DATETIME:
      /** formatTraceTableDate 按值的字符串长度自适应时间单位，转 Number 会丢精度，故透传原值 */
      return value => formatTraceTableDate(value as number | string);
    case RumFieldDisplayEnum.DURATION:
      /** 非数值项原样展示，避免出现 NaN；单位缺省（含空串）按 us 处理 */
      return value => {
        const num = Number(value);
        if (!Number.isFinite(num)) return String(value);
        return formatDuration(num, '', 2, (unit || 'us') as 'ms' | 'us');
      };
    default:
      if (unit) return value => formatUnitValue(value, unit);
      /** 与默认取值逻辑保持一致：结构化值序列化为文本，标量值优先取后台声明的枚举别名 */
      return value =>
        typeof value === 'object' ? JSON.stringify(value) : (getFieldOptionAlias(field, value) ?? String(value));
  }
}

/**
 * @description 取字段元数据声明的枚举别名（option_values），未声明枚举或无匹配项时返回 undefined。
 *              枚举 value 声明为 string，行数据实际可能是 number / boolean，统一字符串化比较。
 * @param {IRumField | undefined} field 字段元数据
 * @param {unknown} value 原始值
 * @returns {string | undefined} 后台映射别名
 */
function getFieldOptionAlias(field: IRumField | undefined, value: unknown): string | undefined {
  return field?.option_values?.find(item => `${item.value}` === `${value}`)?.alias;
}
