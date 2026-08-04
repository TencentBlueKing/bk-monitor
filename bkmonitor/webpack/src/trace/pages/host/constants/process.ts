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

import { ProcessDetailTabEnum, ProcessPortStatusEnum } from './enum';

/** 端口状态 → 展示配置（圆点颜色 + 名称，与采集状态风格保持一致） */
export const PROCESS_PORT_STATUS_MAP: Record<number, { color: string; name: string }> = {
  [ProcessPortStatusEnum.Normal]: { name: window.i18n.t('正常'), color: '#2dcb56' },
  [ProcessPortStatusEnum.Abnormal]: { name: window.i18n.t('异常'), color: '#ea3636' },
};

/** 进程表格溢出省略单元格类名（配合 useTableEllipsis 事件委托，溢出时弹 tooltip） */
export const PROCESS_LIST_ELLIPSIS_CELL_CLASS = 'process-list-ellipsis-cell';

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
  /** 列名（i18n key） */
  name: string;
  /** 是否可排序 */
  sortable?: boolean;
  /** 单元格渲染类型，驱动表格 View 选择渲染器 */
  type: 'cpu' | 'fileHandle' | 'host' | 'instanceCount' | 'memory' | 'name' | 'port' | 'text' | 'uptime';
  /** 列宽 */
  width?: number;
}

/** 进程列表全部列配置 */
export const PROCESS_LIST_COLUMNS: IProcessColumnConfig[] = [
  { id: 'name', name: window.i18n.t('进程名'), type: 'name', checked: true, disabled: true, width: 220 },
  {
    id: 'instanceCount',
    name: window.i18n.t('实例数'),
    type: 'instanceCount',
    checked: true,
    sortable: true,
    align: 'right',
    width: 80,
  },
  { id: 'user', name: window.i18n.t('运行用户'), type: 'text', checked: true, width: 120 },
  { id: 'cpuUsage', name: window.i18n.t('CPU 总占用'), type: 'cpu', checked: true, sortable: true, width: 160 },
  { id: 'memRss', name: window.i18n.t('RSS 总内存'), type: 'memory', checked: true, sortable: true, width: 160 },
  { id: 'fdNum', name: window.i18n.t('文件句柄'), type: 'fileHandle', checked: true, sortable: true, width: 160 },
  { id: 'uptime', name: window.i18n.t('运行时长范围'), type: 'uptime', checked: true, width: 100 },
];

/** 进程详情二级 Tab（Profiling 本期未开发，点击展示占位） */
export const PROCESS_DETAIL_TABS = [
  { id: ProcessDetailTabEnum.METRIC, label: window.i18n.t('指标视图'), icon: 'icon-zhibiaojiansuo' },
  { id: ProcessDetailTabEnum.PROFILING, label: window.i18n.t('Profiling'), icon: 'icon-profiling' },
] as const;
