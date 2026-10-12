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

import {
  getValueFormat,
  getValueFormatterIndex,
  toFixedUnit,
} from 'monitor-ui/monitor-echarts/valueFormats/valueFormats';

/** 带单位数值统一保留的小数位数 */
const UNIT_VALUE_DECIMALS = 2;

/**
 * 后端 field_unit 到量纲表单位 id 的别名映射。
 * 量纲表（valueFormats/categories）里时间用的是 µs（U+00B5）而非 us、数据量用的是 bytes 而非 byte，
 * 未登记的单位（ms / s / mbytes 等）本身就是合法 id，直接透传。
 */
const UNIT_ID_ALIAS: Record<string, string> = {
  byte: 'bytes',
  bytes: 'bytes',
  gb: 'decgbytes',
  gib: 'gbytes',
  kb: 'deckbytes',
  kib: 'kbytes',
  mb: 'decmbytes',
  mib: 'mbytes',
  pb: 'decpbytes',
  pib: 'pbytes',
  tb: 'dectbytes',
  tib: 'tbytes',
  us: 'µs',
};

/** getValueFormat 内建的单位语法前缀（与 use-echarts 图表侧识别范围保持一致） */
const UNIT_FORMAT_PREFIXES: string[] = ['prefix', 'time', 'si', 'count', 'currency'];

/**
 * @description 判断单位是否为 getValueFormat 能正确识别的量纲表 id 或内建语法（prefix:/time:/si:/count:/currency:）
 * @param {string} unitId 归一化后的单位标识
 * @returns {boolean} 命中量纲表或内建语法返回 true，否则 false（应走 toFixedUnit 兜底，避免退化为 short）
 */
const isKnownUnitId = (unitId: string): boolean => {
  if (getValueFormatterIndex()[unitId]) return true;
  const colonIdx = unitId.indexOf(':');
  if (colonIdx > 0) {
    return UNIT_FORMAT_PREFIXES.includes(unitId.slice(0, colonIdx));
  }
  return false;
};

/**
 * @description 带单位数值的单位自适应展示，量纲换算与 explore-chart（use-echarts）共用 getValueFormat
 * @param {unknown} value 原始值
 * @param {string} unit 原始值单位（字段的 field_unit，如 us / ms / bytes / GiB）
 * @returns {string} 自适应单位后的展示文本，如 1234 ms → '1.23 s'、1048576 bytes → '1 MiB'
 */
export const formatUnitValue = (value: unknown, unit: string): string => {
  if (value === null || value === undefined || value === '') return '';
  const num = Number(value);
  /** 非数值（如单位标错的字符串字段）不换算，避免渲染成 NaN */
  if (!Number.isFinite(num)) return String(value);
  const unitId = UNIT_ID_ALIAS[unit.toLowerCase()] ?? unit;
  /**
   * 单位不在量纲表内且非 getValueFormat 内建语法（prefix:/time:/si:/count:/currency:）时，
   * getValueFormat 会静默退化为 short（1000 进制 K / Mil），数值含义被篡改，故显式兜底为不换算。
   * use-echarts 直接 getValueFormat(unit) 未做此兜底，图表侧存在同样隐患。
   */
  const formatter = isKnownUnitId(unitId) ? getValueFormat(unitId) : toFixedUnit(unit);
  const { text, suffix } = formatter(num, UNIT_VALUE_DECIMALS);
  return `${text}${suffix || ''}`;
};
