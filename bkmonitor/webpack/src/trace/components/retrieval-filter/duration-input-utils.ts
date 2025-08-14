/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
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
/**
 * 将时间数值格式化为带单位的时间字符串
 * @param value - 要格式化的时间数值
 * @param baseUnit - 基础单位，默认为'μs'（微秒）
 * @returns 格式化后的时间字符串，如"1.5s"、"500ms"等
 */
export function formatDuration(value: number, baseUnit = 'μs'): string {
  if (!value) return '';
  let units = [
    { unit: 'd', value: 86400000000 },
    { unit: 'h', value: 3600000000 },
    { unit: 'm', value: 60000000 },
    { unit: 's', value: 1000000 },
    { unit: 'ms', value: 1000 },
    { unit: 'μs', value: 1 },
    { unit: 'ns', value: 0.001 },
  ];
  if (baseUnit === 'ms') {
    units = [
      { unit: 'd', value: 86400000 },
      { unit: 'h', value: 3600000 },
      { unit: 'm', value: 60000 },
      { unit: 's', value: 1000 },
      { unit: 'ms', value: 1 },
      { unit: 'μs', value: 0.001 },
      { unit: 'ns', value: 0.000001 },
    ];
  }

  for (const { unit, value: unitValue } of units) {
    if (Math.abs(value) >= unitValue) {
      const result = value / unitValue;
      // 保留最多6位小数，并去除末尾的0
      const formatted = Number.parseFloat(result.toFixed(6)).toString();
      return `${formatted}${unit}`;
    }
  }

  return `${value}ms`; // 默认返回ms
}
/**
 * 检查字符串是否为有效的时间格式（数值+单位）
 * @param str - 要检查的字符串
 * @returns 是否为有效时间格式
 */
export function isValidTimeFormat(str: string, baseUnit = 'μs'): boolean {
  // 正则解释：
  // ^[\d.]+ - 以数字或小数点开头（至少一个）
  // (ns|μs|ms|s|m|h|d)$ - 以指定单位结尾
  if (['μs', 'us'].includes(baseUnit)) {
    return /^[\d.]+(μs|us|ms|s|m|h|d)$/.test(str);
  }
  return /^[\d.]+(ns|μs|us|ms|s|m|h|d)$/.test(str);
}

/**
 * 将时间字符串转换为数值（基于指定基础单位）
 * @param timeStr - 时间字符串，格式为"数值+单位"，例如："1.5s"、"500ms"
 * @param baseUnit - 基础单位，默认为'μs'（微秒），可选'ms'（毫秒）
 * @returns 转换后的数值，基于基础单位
 */
export function parseDuration(timeStr: string, baseUnit = 'μs'): number {
  if (!timeStr) return 0;
  let unitMap: Record<string, number> = {
    ns: 0.001,
    μs: 1,
    us: 1,
    ms: 1000,
    s: 1000000,
    m: 60000000,
    h: 3600000000,
    d: 86400000000,
  };
  if (baseUnit === 'ms') {
    unitMap = {
      ns: 0.000001,
      μs: 0.001,
      us: 0.001,
      ms: 1,
      s: 1000,
      m: 60000,
      h: 3600000,
      d: 86400000,
    };
  }

  // 匹配数字和单位，如 "1.5s" -> ["1.5", "s"]
  const match = timeStr.match(/^([\d.]+)(ns|μs|us|ms|s|m|h|d)$/);
  if (!match) return 0;

  const value = Number.parseFloat(match[1]);
  const unit = match[2];

  return value * (unitMap[unit] || 1);
}
