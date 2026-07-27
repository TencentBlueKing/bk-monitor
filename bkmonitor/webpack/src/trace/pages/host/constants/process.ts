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

import { EProcessPortStatus } from '../types/process';

/** 端口状态 → 展示配置（圆点颜色 + 名称，与采集状态风格保持一致） */
export const PROCESS_PORT_STATUS_MAP: Record<number, { color: string; name: string }> = {
  [EProcessPortStatus.Normal]: { name: window.i18n.t('正常'), color: '#2dcb56' },
  [EProcessPortStatus.Abnormal]: { name: window.i18n.t('异常'), color: '#ea3636' },
  [EProcessPortStatus.Normal]: { name: window.i18n.t('正常'), color: '#2dcb56' },
  [EProcessPortStatus.Abnormal]: { name: window.i18n.t('异常'), color: '#ea3636' },
};

/** 进程表格列定义 */
export interface IProcessColumnConfig {
  /** 单元格对齐方式（数值列通常右对齐） */
  align?: 'center' | 'left' | 'right';
  /** 是否默认展示 */
  checked: boolean;
  /** 是否禁止在「字段设置」中取消（进程名列固定展示） */
  disabled?: boolean;
  /** 字段 key */
  id: string;
  /** 列宽 */
  minWidth?: number;
  /** 列名（i18n key） */
  name: string;
  /** 是否可排序 */
  sortable?: boolean;
  /** 单元格渲染类型，驱动表格 View 选择渲染器 */
  type: 'cpu' | 'fileHandle' | 'host' | 'instanceCount' | 'memory' | 'name' | 'port' | 'text' | 'uptime';
}

/** 进程列表全部列配置 */
export const PROCESS_LIST_COLUMNS: IProcessColumnConfig[] = [
  { id: 'name', name: window.i18n.t('进程名'), type: 'name', checked: true, disabled: true, minWidth: 220 },
  {
    id: 'instanceCount',
    name: window.i18n.t('实例数'),
    type: 'instanceCount',
    checked: true,
    sortable: true,
    align: 'right',
    minWidth: 100,
  },
  { id: 'user', name: window.i18n.t('运行用户'), type: 'text', checked: true, minWidth: 120 },
  { id: 'cpuUsage', name: window.i18n.t('CPU 总占用'), type: 'cpu', checked: true, sortable: true, minWidth: 160 },
  { id: 'memRss', name: window.i18n.t('RSS 总内存'), type: 'memory', checked: true, sortable: true, minWidth: 160 },
  { id: 'fdNum', name: window.i18n.t('文件句柄'), type: 'fileHandle', checked: true, sortable: true, minWidth: 160 },
  { id: 'uptime', name: window.i18n.t('运行时长范围'), type: 'uptime', checked: true, minWidth: 140 },
];

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

/** 进程详情二级 Tab（Profiling 本期未开发，点击展示占位） */
export const PROCESS_DETAIL_TABS = [
  { id: 'metric', label: '指标视图', icon: 'icon-zhibiaojiansuo' },
  { id: 'profiling', label: 'Profiling', icon: 'icon-profiling' },
] as const;

/** 进程详情二级 Tab 取值 */
export type ProcessDetailTab = (typeof PROCESS_DETAIL_TABS)[number]['id'];

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
