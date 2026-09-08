import dayjs from 'dayjs';

import { EMPTY_TEXT } from '../constants';

const MICROSECONDS_PER_MS = 1000;
const MICROSECONDS_PER_SECOND = 1e6;

/** Token 缩写单位，按阈值从大到小匹配 */
const TOKEN_UNITS: [number, string][] = [
  [1e9, 'B'],
  [1e6, 'M'],
  [1e3, 'K'],
];

/** 微秒时间戳 → 'YYYY-MM-DD HH:mm:ss'，跟随全局时区设置 */
export function formatMicroTime(microseconds: number): string {
  if (!microseconds) return EMPTY_TEXT;
  return dayjs.tz(dayjs(microseconds / MICROSECONDS_PER_MS)).format('YYYY-MM-DD HH:mm:ss');
}

/** 微秒耗时 → '1.42s' */
export function formatElapsed(microseconds: number): string {
  if (!Number.isFinite(microseconds)) return EMPTY_TEXT;
  return `${(microseconds / MICROSECONDS_PER_SECOND).toFixed(2)}s`;
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
