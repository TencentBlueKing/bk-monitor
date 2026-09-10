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

/** 支持作为基础单位的字节单位 */
export type TBytesBaseUnit = 'B' | 'GiB' | 'KiB' | 'MiB' | 'TiB';

/** 支持的字节单位（从小到大），1024 进制 */
export const BYTES_UNITS = ['B', 'KiB', 'MiB', 'GiB', 'TiB'] as const;

/** 输入框支持输入的单位提示文案 */
export const BYTES_UNIT_TIPS = BYTES_UNITS.join(', ');

/** 单位 -> 换算系数（小写 key，解析时统一转小写匹配，支持大小写混写；k/kb、m/mb 等简写别名一并收录，按 1024 进制换算） */
const BYTES_UNIT_MAP: Record<string, number> = {
  b: 1,
  k: 1024,
  kb: 1024,
  kib: 1024,
  m: 1024 ** 2,
  mb: 1024 ** 2,
  mib: 1024 ** 2,
  g: 1024 ** 3,
  gb: 1024 ** 3,
  gib: 1024 ** 3,
  t: 1024 ** 4,
  tb: 1024 ** 4,
  tib: 1024 ** 4,
};

/** 匹配 "数值+单位"，如 "1.5MiB"；单位可省略（按 baseUnit 计），单位部分长的在前，避免被 b / k 提前匹配 */
const BYTES_VALUE_REG = /^([\d.]+)\s*(tib|tb|t|gib|gb|g|mib|mb|m|kib|kb|k|b)?$/i;

/**
 * 将字节数值格式化为带单位的字符串，自动选择最合适（最大）的单位
 * @param value - 要格式化的字节数（以 baseUnit 为单位的原始值）
 * @param baseUnit - 数值的基础单位，默认为'B'（字节）
 * @returns 格式化后的字符串，如"1.5MiB"、"512B"，0 或空值返回空字符串
 */
export function formatBytes(value: number, baseUnit: TBytesBaseUnit = 'B'): string {
  if (!value) return '';
  const bValue = value * getUnitToB(baseUnit);
  for (let i = BYTES_UNITS.length - 1; i >= 0; i--) {
    const unit = BYTES_UNITS[i];
    const unitToB = getUnitToB(unit);
    if (Math.abs(bValue) >= unitToB) {
      // 保留最多6位小数，并去除末尾的0
      const formatted = Number.parseFloat((bValue / unitToB).toFixed(6)).toString();
      return `${formatted}${unit}`;
    }
  }
  return `${value}${baseUnit}`;
}

/**
 * 将用户输入的字节串规范化为标准展示格式（防呆）
 * 兼容大小写混写（1.5MIB）、简写单位（1k / 1KB / 1mb）以及不带单位的纯数字（1024 按 baseUnit 计）
 * @param str - 用户输入的原始字符串
 * @param baseUnit - 数值的基础单位，默认为'B'（字节）
 * @returns 规范化后的字符串，如"1KiB"；无法识别时返回空字符串
 */
export function normalizeBytesInput(str: string, baseUnit: TBytesBaseUnit = 'B'): string {
  if (!str) return '';
  const match = String(str).trim().match(BYTES_VALUE_REG);
  if (!match) return '';
  const value = Number.parseFloat(match[1]);
  if (!Number.isFinite(value)) return '';
  // 不带单位时数值本身就是 baseUnit 下的值，带单位则先换算到 baseUnit，再统一按最合适的单位格式化
  const unitToB = match[2] ? getUnitToB(match[2]) : getUnitToB(baseUnit);
  return formatBytes((value * unitToB) / getUnitToB(baseUnit), baseUnit);
}

/**
 * 将字节字符串转换为数值（换算到指定基础单位）
 * @param bytesStr - 字节字符串，格式为"数值+单位"，例如："1.5MiB"、"512B"，单位省略时按 baseUnit 计
 * @param baseUnit - 转换后的基础单位，默认为'B'（字节）
 * @returns 转换后的数值，解析失败返回 0
 */
export function parseBytes(bytesStr: string, baseUnit: TBytesBaseUnit = 'B'): number {
  if (!bytesStr) return 0;
  const match = bytesStr.match(BYTES_VALUE_REG);
  if (!match) return 0;
  const value = Number.parseFloat(match[1]);
  // 不带单位时数值本身就是 baseUnit 下的值，带单位才做换算
  const unitToB = match[2] ? getUnitToB(match[2]) : getUnitToB(baseUnit);
  return (value * unitToB) / getUnitToB(baseUnit);
}

/** 取单位相对字节(B)的换算系数，统一转小写匹配，未知单位按 B 处理 */
function getUnitToB(unit: string): number {
  return BYTES_UNIT_MAP[unit.toLowerCase()] ?? 1;
}
