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
import dayjs from 'dayjs';

import { EMPTY_TEXT } from '../constants';

const MICROSECONDS_PER_MS = 1000;
const ELAPSED_UNITS: [number, string][] = [
  [86400e6, 'd'],
  [3600e6, 'h'],
  [60e6, 'm'],
  [1e6, 's'],
  [1000, 'ms'],
  [1, 'μs'],
];

/** Token 缩写单位，按阈值从大到小匹配 */
const TOKEN_UNITS: [number, string][] = [
  [1e9, 'B'],
  [1e6, 'M'],
  [1e3, 'K'],
];

/**
 * 与 Trace formatDuration 的展示口径一致：分钟及以上保留两个相邻单位，次单位四舍五入。
 * 秒及以下使用小数；完整模式保留所有非零单位，用于悬停详情。
 */
export function formatElapsed(microseconds: number, detailed = false): string {
  if (!Number.isFinite(microseconds)) return EMPTY_TEXT;
  const duration = Math.max(0, microseconds);
  if (!detailed) {
    const index = ELAPSED_UNITS.findIndex(([size]) => duration >= size);
    const [size, unit] = ELAPSED_UNITS[index < 0 ? ELAPSED_UNITS.length - 1 : index];
    if (size <= 1e6) return `${Number((duration / size).toFixed(2))}${unit}`;

    const [secondarySize, secondaryUnit] = ELAPSED_UNITS[index + 1];
    const primaryValue = Math.floor(duration / size);
    const secondaryValue = Math.round((duration % size) / secondarySize);
    if (secondaryValue >= size / secondarySize) return `${primaryValue + 1}${unit}`;
    return secondaryValue ? `${primaryValue}${unit} ${secondaryValue}${secondaryUnit}` : `${primaryValue}${unit}`;
  }

  let remaining = Math.round(duration);
  const parts: string[] = [];
  for (const [size, unit] of ELAPSED_UNITS) {
    if (remaining < size) continue;
    const value = Math.floor(remaining / size);
    remaining %= size;
    parts.push(`${value}${unit}`);
  }

  return parts.join(' ') || '0μs';
}

/** 微秒时间戳 → 'YYYY-MM-DD HH:mm:ssZZ'，跟随全局时区设置 */
export function formatMicroTime(microseconds: number): string {
  if (!microseconds) return EMPTY_TEXT;
  return dayjs.tz(dayjs(microseconds / MICROSECONDS_PER_MS)).format('YYYY-MM-DD HH:mm:ssZZ');
}

/** Token 数量 → '34.2K' / '28.2M'，不足 1000 时原样输出 */
export function formatTokens(value: number): string {
  if (!Number.isFinite(value)) return EMPTY_TEXT;
  for (const [threshold, unit] of TOKEN_UNITS) {
    if (value >= threshold) {
      return `${(value / threshold).toFixed(1)}${unit}`;
    }
  }
  return `${value}`;
}
