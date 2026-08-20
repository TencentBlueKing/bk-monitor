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

import type { ProcessItem } from '../types/process';

/**
 * 进程指标进度条颜色（参考主机列表指标列：>85 warn、>=95 danger、其余 success）
 * @param value 指标使用率百分比（CPU / 内存 / 文件句柄等）
 */
export const getProcessBarColor = (value: number): string => {
  if (value >= 95) return '#ea3636';
  if (value > 85) return '#f59500';
  return '#21a380';
};

/** 运行时长秒数 → 展示文案（列表按小时，超过 1 天按天） */
export const formatUptime = (seconds: null | number | undefined): string => {
  if (seconds == null || !Number.isFinite(seconds) || seconds < 0) {
    return '--';
  }
  const hours = seconds / 3600;
  if (hours >= 24) {
    return `${+(hours / 24).toFixed(1)} d`;
  }
  return `${+hours.toFixed(1)} h`;
};

/** 同名进程组运行时长范围 → 展示文案；单实例或单边有效时展示单值。 */
export const formatUptimeRange = (
  minSeconds: null | number | undefined,
  maxSeconds: null | number | undefined
): string => {
  const validMin = minSeconds != null && Number.isFinite(minSeconds) && minSeconds >= 0;
  const validMax = maxSeconds != null && Number.isFinite(maxSeconds) && maxSeconds >= 0;
  if (!validMin && !validMax) {
    return '--';
  }
  if (!validMin) {
    return formatUptime(maxSeconds);
  }
  if (!validMax) {
    return formatUptime(minSeconds);
  }
  const minText = formatUptime(minSeconds);
  const maxText = formatUptime(maxSeconds);
  return minText === maxText ? minText : `${minText} - ${maxText}`;
};

/** 格式化进程行运行时长，并兼容旧接口仅返回 uptime 的响应。 */
export const formatProcessUptimeRange = (process: Pick<ProcessItem, 'uptime' | 'uptimeMax' | 'uptimeMin'>): string =>
  formatUptimeRange(process.uptimeMin ?? process.uptime, process.uptimeMax ?? process.uptime);

/**
 * 将后台返回的小数使用率格式化为前端百分比展示
 * @param value 后台返回的小数（如 0.1532）或字符串
 * @returns 格式化后的百分比对象（text: 展示文案，value: 原始百分比数值，width: 进度条宽度）
 */
export const formatPercent = (
  value: null | number | string | undefined
): { text: string; value: null | number; width: number } => {
  const parsed = typeof value === 'string' ? parseFloat(value) : value;
  if (parsed == null || !Number.isFinite(parsed)) {
    return { text: '--', value: null, width: 0 };
  }
  const num = parsed * 100;
  return {
    text: `${num.toFixed(2)}%`,
    value: num,
    width: Math.min(Math.max(num, 0), 100),
  };
};

/** 物理内存 RSS 字节数 → 展示文案（如 92 MiB） */
export const formatMemRss = (bytes: null | number | undefined): string => {
  if (bytes == null || !Number.isFinite(bytes) || bytes < 0) {
    return '--';
  }
  const units = ['B', 'KiB', 'MiB', 'GiB', 'TiB'];
  let value = bytes;
  let index = 0;
  while (value >= 1024 && index < units.length - 1) {
    value /= 1024;
    index += 1;
  }
  return `${+value.toFixed(value >= 100 || index === 0 ? 0 : 1)} ${units[index]}`;
};

/** 进程图例默认展示进程名，仅在查询按 PID 分组时追加 PID。 */
export const formatProcessSeriesAlias = (dimensions: Record<string, unknown> | undefined, fallback: string): string => {
  if (!dimensions) {
    return fallback;
  }
  const parts = [dimensions.display_name, dimensions.pid].filter(
    value => value !== undefined && value !== null && value !== ''
  );
  return parts.length ? parts.join('|') : fallback;
};

/**
 * 运行时长秒数 → 进程详情展示文案（如 `2.19d (2024-10-22 14:00:00)`）。
 * 起始时间按「观测时刻 - 运行时长」推算，对齐历史查询语义。
 */
export const formatProcessUptimeDetail = (
  seconds: null | number | undefined,
  observedAtSeconds = dayjs().unix()
): string => {
  if (seconds == null || !Number.isFinite(seconds) || seconds < 0) {
    return '--';
  }
  const startTime = dayjs.unix(observedAtSeconds).subtract(seconds, 'second').format('YYYY-MM-DD HH:mm:ss');
  const days = seconds / 86400;
  const duration = days >= 1 ? `${+days.toFixed(2)}d` : `${+(seconds / 3600).toFixed(2)}h`;
  return `${duration} (${startTime})`;
};
