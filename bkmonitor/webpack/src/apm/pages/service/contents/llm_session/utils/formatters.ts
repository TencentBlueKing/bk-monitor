import dayjs from 'dayjs';

import { EMPTY_TEXT } from '../constants';

const MICROSECONDS_PER_MS = 1000;
const MICROSECONDS_PER_SECOND = 1e6;
const SECONDS_PER_MINUTE = 60;
const SECONDS_PER_HOUR = 3600;
const SECONDS_PER_DAY = 86400;

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

/**
 * 微秒耗时 → 按秒、分钟、小时、天自动进位。
 * 不足 1 分钟保留两位小数秒；更大时长只展示非 0 单位，如 '1.42s' / '3m 20s' / '2h 5m 3s' / '1d 3h'。
 */
export function formatElapsed(microseconds: number): string {
  if (!Number.isFinite(microseconds)) return EMPTY_TEXT;

  const totalSeconds = microseconds / MICROSECONDS_PER_SECOND;
  const roundedSeconds = Number(totalSeconds.toFixed(2));
  if (Math.abs(roundedSeconds) < SECONDS_PER_MINUTE) {
    return `${roundedSeconds.toFixed(2)}s`;
  }

  let remaining = Math.round(totalSeconds);
  const parts: string[] = [];
  const units: [number, string][] = [
    [SECONDS_PER_DAY, 'd'],
    [SECONDS_PER_HOUR, 'h'],
    [SECONDS_PER_MINUTE, 'm'],
    [1, 's'],
  ];

  for (const [size, unit] of units) {
    if (remaining < size) continue;
    const value = Math.floor(remaining / size);
    remaining %= size;
    parts.push(`${value}${unit}`);
  }

  return parts.join(' ') || '0s';
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
