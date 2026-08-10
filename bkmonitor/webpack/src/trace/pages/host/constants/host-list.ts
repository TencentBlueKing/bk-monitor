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

import { EFieldType } from '../../../components/retrieval-filter/typing';
import { HOST_FILTER_FIELDS_ENUM } from './constants';

import type { IFilterField } from '../../../components/retrieval-filter/typing';
import type { IHostQuickCard, IHostStatusConfig, IStatusTipsConfig } from '../types';

/** 默认每页条数（设计稿：默认每页 50 条） */
export const HOST_LIST_DEFAULT_PAGE_SIZE = 50;
/** 每页条数候选 */
export const HOST_LIST_PAGE_SIZE_LIST = [10, 20, 50, 100];
/** 表格行高（设计稿：36 行高，显示更多内容） */
export const HOST_LIST_ROW_HEIGHT = 36;
/** 主机列表溢出省略单元格类名（配合 useTableEllipsis 事件委托，溢出时弹 tooltip） */
export const HOST_LIST_ELLIPSIS_CELL_CLASS = 'host-list-ellipsis-cell';
/** 快捷过滤卡片的指标阈值（超过该值计入分类） */
export const HOST_METRIC_OVER_THRESHOLD = 80;

/** 采集状态 → 展示配置（圆点颜色 + 名称，和其他模块保持一致） */
export const HOST_STATUS_MAP: Record<number, IHostStatusConfig> = {
  [-1]: { name: window.i18n.t('未知'), color: '#c4c6cc', backgroundColor: '#979ba529' },
  0: { name: window.i18n.t('正常'), color: '#2dcb56', backgroundColor: '#DAF6E5' },
  2: { name: window.i18n.t('无 Agent'), color: '#c4c6cc', backgroundColor: '#979ba529' },
  3: { name: window.i18n.t('无数据上报'), color: '#ea3636', backgroundColor: '#FFEBEB' },
};

/** 快捷过滤卡片列表（点击整卡过滤，再次点击取消） */
export const HOST_QUICK_CARD_LIST: IHostQuickCard[] = [
  { key: 'alarm', name: window.i18n.t('告警中的主机') },
  { key: 'cpu', name: window.i18n.t('CPU 使用率超 80 %') },
  { key: 'mem', name: window.i18n.t('应用内存使用率超 80 %') },
  { key: 'disk', name: window.i18n.t('磁盘空间使用率超 80 %') },
];

/** 指标列 key（这些列展示「聚合方式 + 数值 + 进度条」） */
export const HOST_METRIC_COLUMN_KEYS = ['cpu_usage', 'mem_usage', 'disk_in_use', 'io_util', 'psc_mem_usage'] as const;
export type HostMetricColumnKey = (typeof HOST_METRIC_COLUMN_KEYS)[number];

/** 表格列定义 */
export interface IHostColumnConfig {
  /** 是否默认展示 */
  checked: boolean;
  /** 是否禁止在字段设置中取消（主机列固定展示） */
  disabled?: boolean;
  /** 固定列 */
  fixed?: 'left' | 'right';
  /** 字段 key */
  id: string;
  /** 列宽 */
  minWidth?: number;
  /** 列名（i18n key） */
  name: string;
  /** 是否可排序 */
  sortable?: boolean;
  /** 单元格渲染类型，驱动表格 View 选择渲染器 */
  type: 'alarm' | 'checkbox' | 'cluster' | 'ip' | 'metric' | 'module' | 'process' | 'status' | 'text';
  /** 列宽 */
  width?: number;
}

/**
 * 主机列表全部列配置（默认勾选项对齐设计稿主视图，其余可在「字段设置」中开启）。
 */
export const HOST_LIST_COLUMNS: IHostColumnConfig[] = [
  { id: 'id', name: 'ID', type: 'checkbox', checked: true, disabled: true, width: 65, fixed: 'left' },
  {
    id: 'host_display_name',
    name: window.i18n.t('主机'),
    type: 'ip',
    checked: true,
    disabled: true,
    minWidth: 200,
    fixed: 'left',
  },
  { id: 'bk_host_innerip', name: window.i18n.t('内网 IP'), type: 'text', checked: true, minWidth: 130 },
  { id: 'bk_host_innerip_v6', name: window.i18n.t('内网 IPv6'), type: 'text', checked: false, minWidth: 180 },
  { id: 'bk_host_outerip', name: window.i18n.t('外网 IP'), type: 'text', checked: false, minWidth: 130 },
  { id: 'bk_host_name', name: window.i18n.t('主机名'), type: 'text', checked: false, minWidth: 140 },
  { id: 'bk_os_name', name: window.i18n.t('OS 名称'), type: 'text', checked: false, minWidth: 120 },
  { id: 'bk_cloud_name', name: window.i18n.t('管控区域'), type: 'text', checked: false, minWidth: 120 },
  { id: 'status', name: window.i18n.t('采集状态'), type: 'status', checked: true, minWidth: 150 },
  { id: 'bk_cluster', name: window.i18n.t('集群名'), type: 'cluster', checked: false, minWidth: 140 },
  { id: 'bk_inst_name', name: '模块名', type: 'module', checked: false, minWidth: 140 },
  { id: 'alarm_count', name: '未恢复的告警', type: 'alarm', checked: true, sortable: true, minWidth: 140 },
  { id: 'cpu_usage', name: window.i18n.t('CPU 使用率'), type: 'metric', checked: true, sortable: true, minWidth: 156 },
  {
    id: 'mem_usage',
    name: window.i18n.t('应用内存使用率'),
    type: 'metric',
    checked: true,
    sortable: true,
    minWidth: 156,
  },
  {
    id: 'disk_in_use',
    name: window.i18n.t('磁盘空间使用率'),
    type: 'metric',
    checked: true,
    sortable: true,
    minWidth: 156,
  },
  { id: 'io_util', name: window.i18n.t('磁盘IO使用率'), type: 'metric', checked: false, sortable: true, minWidth: 156 },
  {
    id: 'psc_mem_usage',
    name: window.i18n.t('物理内存使用率'),
    type: 'metric',
    checked: false,
    sortable: true,
    minWidth: 156,
  },
  {
    id: 'cpu_load',
    name: window.i18n.t('CPU 五分钟负载'),
    type: 'text',
    checked: false,
    sortable: true,
    minWidth: 140,
  },
  { id: 'display_name', name: window.i18n.t('进程'), type: 'process', checked: true, minWidth: 198 },
];

/** 数值类指标过滤操作符（支持 > >= < <= =） */
export const NUMBER_METHODS = [
  { value: 'gt', alias: '>' },
  { value: 'gte', alias: '>=' },
  { value: 'lt', alias: '<' },
  { value: 'lte', alias: '<=' },
  { value: 'eq', alias: '=' },
];

/** 枚举/字符串类过滤操作符（包含/不包含） */
const ENUM_METHODS = [
  { value: 'eq', alias: '=' },
  { value: 'ne', alias: '!=' },
];
/** 文本类字段过滤操作符：仅支持「包含」模糊匹配（用于主机 ID / IP 等文本字段） */
const TEXT_METHODS = [{ value: 'include', alias: window.i18n.t('包含') }];

/**
 * retrieval-filter 过滤字段定义（候选项由前端全量数据动态提供，见 getValueFn）。
 * 与旧版主机监控字段保持一致，但仅保留新版列表实际支持的过滤维度。
 */
export const HOST_FILTER_FIELDS: IFilterField[] = [
  {
    name: HOST_FILTER_FIELDS_ENUM.bkHostId,
    alias: window.i18n.t('主机'),
    type: EFieldType.text,
    methods: TEXT_METHODS,
    isEnableOptions: false,
  },
  {
    name: HOST_FILTER_FIELDS_ENUM.bkHostInnerIpV6,
    alias: window.i18n.t('内网 IPv6'),
    type: EFieldType.text,
    methods: TEXT_METHODS,
    isEnableOptions: false,
  },
  {
    name: HOST_FILTER_FIELDS_ENUM.bkHostOuterIpV6,
    alias: window.i18n.t('外网 IPv6'),
    type: EFieldType.text,
    methods: TEXT_METHODS,
    isEnableOptions: false,
  },
  {
    name: HOST_FILTER_FIELDS_ENUM.bkHostInnerIp,
    alias: window.i18n.t('内网 IP'),
    type: EFieldType.text,
    methods: TEXT_METHODS,
    isEnableOptions: false,
  },
  {
    name: HOST_FILTER_FIELDS_ENUM.bkHostOuterIp,
    alias: window.i18n.t('外网 IP'),
    type: EFieldType.text,
    methods: TEXT_METHODS,
    isEnableOptions: false,
  },
  {
    name: HOST_FILTER_FIELDS_ENUM.status,
    alias: window.i18n.t('采集状态'),
    type: EFieldType.keyword,
    methods: ENUM_METHODS,
    isEnableOptions: true,
  },
  {
    name: HOST_FILTER_FIELDS_ENUM.bkHostName,
    alias: window.i18n.t('主机名'),
    type: EFieldType.keyword,
    methods: ENUM_METHODS,
    isEnableOptions: true,
  },
  {
    name: HOST_FILTER_FIELDS_ENUM.bkOsName,
    alias: window.i18n.t('OS 名称'),
    type: EFieldType.keyword,
    methods: ENUM_METHODS,
    isEnableOptions: true,
  },
  {
    name: HOST_FILTER_FIELDS_ENUM.bkCloudName,
    alias: window.i18n.t('管控区域'),
    type: EFieldType.keyword,
    methods: ENUM_METHODS,
    isEnableOptions: true,
  },
  {
    name: HOST_FILTER_FIELDS_ENUM.clusterModule,
    alias: window.i18n.t('业务拓扑'),
    type: EFieldType.cascade,
    methods: ENUM_METHODS,
    isEnableOptions: true,
  },
  {
    name: HOST_FILTER_FIELDS_ENUM.bkCluster,
    alias: window.i18n.t('集群名'),
    type: EFieldType.keyword,
    methods: ENUM_METHODS,
    isEnableOptions: true,
  },
  {
    name: HOST_FILTER_FIELDS_ENUM.bkInstName,
    alias: window.i18n.t('模块名'),
    type: EFieldType.keyword,
    methods: ENUM_METHODS,
    isEnableOptions: true,
  },
  {
    name: HOST_FILTER_FIELDS_ENUM.alarmCount,
    alias: window.i18n.t('未恢复告警'),
    type: EFieldType.numberInput,
    methods: NUMBER_METHODS,
    isEnableOptions: false,
  },
  {
    name: HOST_FILTER_FIELDS_ENUM.cpuLoad,
    alias: window.i18n.t('CPU 五分钟负载'),
    type: EFieldType.numberInput,
    methods: NUMBER_METHODS,
    isEnableOptions: false,
  },
  {
    name: HOST_FILTER_FIELDS_ENUM.cpuUsage,
    alias: window.i18n.t('CPU 使用率'),
    type: EFieldType.numberInput,
    methods: NUMBER_METHODS,
    isEnableOptions: false,
  },
  {
    name: HOST_FILTER_FIELDS_ENUM.diskInUse,
    alias: window.i18n.t('磁盘空间使用率'),
    type: EFieldType.numberInput,
    methods: NUMBER_METHODS,
    isEnableOptions: false,
  },
  {
    name: HOST_FILTER_FIELDS_ENUM.ioUtil,
    alias: window.i18n.t('磁盘 IO 使用率'),
    type: EFieldType.numberInput,
    methods: NUMBER_METHODS,
    isEnableOptions: false,
  },
  {
    name: HOST_FILTER_FIELDS_ENUM.memUsage,
    alias: window.i18n.t('应用内存使用率'),
    type: EFieldType.numberInput,
    methods: NUMBER_METHODS,
    isEnableOptions: false,
  },
  {
    name: HOST_FILTER_FIELDS_ENUM.pscMemUsage,
    alias: window.i18n.t('物理内存使用率'),
    type: EFieldType.numberInput,
    methods: NUMBER_METHODS,
    isEnableOptions: false,
  },
  {
    name: HOST_FILTER_FIELDS_ENUM.kBizName,
    alias: window.i18n.t('业务名'),
    type: EFieldType.keyword,
    methods: ENUM_METHODS,
    isEnableOptions: false,
  },
  {
    name: HOST_FILTER_FIELDS_ENUM.displayName,
    alias: window.i18n.t('进程'),
    type: EFieldType.keyword,
    methods: ENUM_METHODS,
    isEnableOptions: true,
  },
];

/** 数值类过滤字段集合（用于 where 匹配时的数值比较分支） */
export const HOST_NUMBER_FILTER_FIELDS = new Set([
  'cpu_usage',
  'mem_usage',
  'disk_in_use',
  'io_util',
  'psc_mem_usage',
  'cpu_load',
  'alarm_count',
]);

/** 主机采集状态 tip 配置（对齐 performance-table statusMap） */
export const HOST_STATUS_TIPS_MAP: Record<number, IStatusTipsConfig> = {
  2: {
    tipsText: window.i18n.t('原因: Agent未安装或者状态异常'),
    linkText: window.i18n.t('前往节点管理处理'),
    linkUrl: `${window.bk_nodeman_host || ''}#/agent-manager/status`,
  },
  3: {
    tipsText: window.i18n.t('原因:bkmonitorbeat未安装或者状态异常'),
    linkText: window.i18n.t('前往节点管理处理'),
    linkUrl: `${window.bk_nodeman_host || ''}#/plugin-manager/list`,
  },
};

/** 进程状态 tip 配置（主机列表表格进程列使用，对齐 performance-table componentStatusMap） */
export const PROCESS_STATUS_TIPS_MAP: Record<number, IStatusTipsConfig> = {
  1: {
    tipsText: window.i18n.t('原因:查看进程本身问题或者检查进程配置是否正常'),
    docLink: 'processMonitor',
  },
  2: {
    tipsText: window.i18n.t('原因:bkmonitorbeat进程采集器未安装或者状态异常'),
    linkText: window.i18n.t('前往节点管理处理'),
    linkUrl: `${window.bk_nodeman_host || ''}#/plugin-manager/list`,
  },
  3: {},
};

/** 指标列表头固定聚合图标映射（列 id -> icon class，对标旧版 table-store headerPreIcon） */
export const HOST_METRIC_HEADER_ICON_MAP: Record<string, string> = {
  cpu_load: 'icon-last',
  cpu_usage: 'icon-last',
  mem_usage: 'icon-last',
  psc_mem_usage: 'icon-last',
  disk_in_use: 'icon-max',
  io_util: 'icon-max',
};
