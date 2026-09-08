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
/** 支持作为基础单位的时间单位，μs / us 等价（后端多返回 us） */
export type TDurationBaseUnit = 'd' | 'h' | 'm' | 'ms' | 's' | 'us' | 'μs';

/** 输入框支持输入的单位提示文案 */
export const DURATION_UNIT_TIPS = 'μs/us, ms, s, m, h, d';

/** 各时间单位相对微秒(μs)的换算系数，统一以 μs 作为换算中介 */
const UNIT_TO_US: Record<string, number> = {
  d: 86400000000,
  h: 3600000000,
  m: 60000000,
  s: 1000000,
  ms: 1000,
  μs: 1,
  us: 1,
  ns: 0.001,
};

/** 展示用单位（从大到小），formatDuration 依次降级挑选最合适的单位 */
const DISPLAY_UNITS = ['d', 'h', 'm', 's', 'ms', 'μs', 'ns'] as const;

/** 匹配 "数值+单位"，如 "1.5s"，单位长的在前避免被 s / m 提前匹配 */
const DURATION_VALUE_REG = /^([\d.]+)(ns|μs|us|ms|s|m|h|d)$/;

/** 基础单位为微秒时不接受更小的 ns，与历史行为保持一致 */
const DURATION_VALUE_WITHOUT_NS_REG = /^[\d.]+(μs|us|ms|s|m|h|d)$/;

/**
 * 将时间数值格式化为带单位的时间字符串，自动选择最合适的展示单位
 * @param value - 要格式化的时间数值（以 baseUnit 为单位的原始值）
 * @param baseUnit - 数值的基础单位，默认为'μs'（微秒）
 * @returns 格式化后的时间字符串，如"1.5s"、"500ms"等，0 或空值返回空字符串
 */
export function formatDuration(value: number, baseUnit: TDurationBaseUnit = 'μs'): string {
  if (!value) return '';
  const usValue = value * getUnitToUs(baseUnit);
  for (const unit of DISPLAY_UNITS) {
    const unitToUs = getUnitToUs(unit);
    if (Math.abs(usValue) >= unitToUs) {
      // 保留最多6位小数，并去除末尾的0
      const formatted = Number.parseFloat((usValue / unitToUs).toFixed(6)).toString();
      return `${formatted}${unit}`;
    }
  }
  return `${value}${baseUnit}`;
}

/**
 * 检查字符串是否为有效的时间格式（数值+单位）
 * @param str - 要检查的字符串
 * @param baseUnit - 基础单位，默认为'μs'（微秒）
 * @returns 是否为有效时间格式
 */
export function isValidTimeFormat(str: string, baseUnit: TDurationBaseUnit = 'μs'): boolean {
  // 正则解释：
  // ^[\d.]+ - 以数字或小数点开头（至少一个）
  // (ns|μs|us|ms|s|m|h|d)$ - 以指定单位结尾
  if (getUnitToUs(baseUnit) <= 1) {
    return DURATION_VALUE_WITHOUT_NS_REG.test(str);
  }
  return DURATION_VALUE_REG.test(str);
}
/**
 * 将时间字符串转换为数值（换算到指定基础单位）
 * @param timeStr - 时间字符串，格式为"数值+单位"，例如："1.5s"、"500ms"
 * @param baseUnit - 转换后的基础单位，默认为'μs'（微秒）
 * @returns 转换后的数值，解析失败返回 0
 */
export function parseDuration(timeStr: string, baseUnit: TDurationBaseUnit = 'μs'): number {
  if (!timeStr) return 0;
  // 匹配数字和单位，如 "1.5s" -> ["1.5", "s"]
  const match = timeStr.match(DURATION_VALUE_REG);
  if (!match) return 0;

  const value = Number.parseFloat(match[1]);
  const unit = match[2];

  return (value * getUnitToUs(unit)) / getUnitToUs(baseUnit);
}

/** 取单位相对微秒的换算系数，未知单位按微秒处理 */
function getUnitToUs(unit: string): number {
  return UNIT_TO_US[unit] ?? 1;
}
