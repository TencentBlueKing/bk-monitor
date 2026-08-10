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

/**
 * 进程指标进度条颜色（参考主机列表指标列：>85 warn、>=95 danger、其余 success）
 * @param value 指标使用率百分比（CPU / 内存 / 文件句柄等）
 */
export const getProcessBarColor = (value: number): string => {
  if (value >= 95) return '#ea3636';
  if (value > 85) return '#f59500';
  return '#21a380';
};

/** 运行时长毫秒数 → 展示文案（列表按小时，超过 1 天按天） */
export const formatUptime = (milliseconds: number): string => {
  if (!(milliseconds > 0)) {
    return '--';
  }
  const seconds = milliseconds / 1000;
  const hours = seconds / 3600;
  if (hours >= 24) {
    return `${+(hours / 24).toFixed(1)} d`;
  }
  return `${+hours.toFixed(1)} h`;
};

/** 物理内存 RSS 字节数 → 展示文案（如 92 MiB） */
export const formatMemRss = (bytes: number): string => {
  if (!(bytes > 0)) {
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

/**
 * 运行时长范围毫秒数 → 进程详情展示文案（如 `2.19d (2024-10-22 14:00:00)`）。
 * 起始时间按「当前时间 - 运行时长」推算，对齐设计稿头部信息。
 */
export const formatProcessUptimeDetail = (milliseconds: number): string => {
  if (!(milliseconds > 0)) {
    return '--';
  }
  const seconds = milliseconds / 1000;
  const startTime = dayjs().subtract(milliseconds, 'millisecond').format('YYYY-MM-DD HH:mm:ss');
  const days = seconds / 86400;
  const duration = days >= 1 ? `${+days.toFixed(2)}d` : `${+(seconds / 3600).toFixed(2)}h`;
  return `${duration} (${startTime})`;
};
