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
import type { EHostAggMethod, IHostQuickCard, IHostStatusConfig } from '../types';

/** 默认每页条数（设计稿：默认每页 50 条） */
export const HOST_LIST_DEFAULT_PAGE_SIZE = 50;
/** 每页条数候选 */
export const HOST_LIST_PAGE_SIZE_LIST = [10, 20, 50, 100];
/** 表格行高（设计稿：36 行高，显示更多内容） */
export const HOST_LIST_ROW_HEIGHT = 36;
/** 快捷过滤卡片的指标阈值（超过该值计入分类） */
export const HOST_METRIC_OVER_THRESHOLD = 80;

/** 采集状态 → 展示配置（圆点颜色 + 名称，和其他模块保持一致） */
export const HOST_STATUS_MAP: Record<number, IHostStatusConfig> = {
  [-1]: { name: '未知', color: '#c4c6cc' },
  0: { name: '正常', color: '#2dcb56' },
  2: { name: '无Agent', color: '#c4c6cc' },
  3: { name: '无数据上报', color: '#ea3636' },
};

/** 快捷过滤卡片列表（点击整卡过滤，再次点击取消） */
export const HOST_QUICK_CARD_LIST: IHostQuickCard[] = [
  { key: 'alarm', icon: 'icon-gaojing', name: '告警中的主机' },
  { key: 'cpu', icon: 'icon-CPU', name: 'CPU使用率超80%' },
  { key: 'mem', icon: 'icon-neicun', name: '应用内存使用率超80%' },
  { key: 'disk', icon: 'icon-cipan', name: '磁盘空间使用率超80%' },
];

/** 指标聚合方式列表（蓝字可点切换，参考容器监控） */
export const HOST_AGG_METHOD_LIST: { id: EHostAggMethod; name: string }[] = [
  { id: 'avg', name: 'avg' },
  { id: 'max', name: 'max' },
  { id: 'min', name: 'min' },
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
  /** 字段 key */
  id: string;
  /** 列宽 */
  minWidth?: number;
  /** 列名（i18n key） */
  name: string;
  /** 是否可排序 */
  sortable?: boolean;
  /** 单元格渲染类型，驱动表格 View 选择渲染器 */
  type: 'alarm' | 'cluster' | 'ip' | 'metric' | 'module' | 'process' | 'status' | 'text';
  /** 列宽 */
  width?: number;
}

/**
 * 主机列表全部列配置（默认勾选项对齐设计稿主视图，其余可在「字段设置」中开启）。
 */
export const HOST_LIST_COLUMNS: IHostColumnConfig[] = [
  { id: 'host_display_name', name: '主机', type: 'ip', checked: true, disabled: true, minWidth: 140 },
  { id: 'bk_host_innerip', name: '内网IP', type: 'text', checked: true, minWidth: 130 },
  { id: 'bk_host_innerip_v6', name: '内网IPv6', type: 'text', checked: false, minWidth: 180 },
  { id: 'bk_host_outerip', name: '外网IP', type: 'text', checked: false, minWidth: 130 },
  { id: 'bk_host_name', name: '主机名', type: 'text', checked: false, minWidth: 140 },
  { id: 'bk_os_name', name: 'OS名称', type: 'text', checked: false, minWidth: 120 },
  { id: 'bk_cloud_name', name: '管控区域', type: 'text', checked: false, minWidth: 120 },
  { id: 'status', name: '采集状态', type: 'status', checked: true, minWidth: 110 },
  { id: 'bk_cluster', name: '集群名', type: 'cluster', checked: false, minWidth: 140 },
  { id: 'bk_inst_name', name: '模块名', type: 'module', checked: false, minWidth: 140 },
  { id: 'alarm_count', name: '未恢复的告警', type: 'alarm', checked: true, sortable: true, minWidth: 120 },
  { id: 'cpu_usage', name: 'CPU使用率', type: 'metric', checked: true, sortable: true, minWidth: 156 },
  { id: 'mem_usage', name: '应用内存使用率', type: 'metric', checked: true, sortable: true, minWidth: 156 },
  { id: 'disk_in_use', name: '磁盘空间使用率', type: 'metric', checked: true, sortable: true, minWidth: 156 },
  { id: 'io_util', name: '磁盘IO使用率', type: 'metric', checked: false, sortable: true, minWidth: 156 },
  { id: 'psc_mem_usage', name: '物理内存使用率', type: 'metric', checked: false, sortable: true, minWidth: 156 },
  { id: 'cpu_load', name: 'CPU五分钟负载', type: 'text', checked: false, sortable: true, minWidth: 140 },
  { id: 'display_name', name: '进程', type: 'process', checked: true, minWidth: 198 },
];

/** 数值类指标过滤操作符（支持 > >= < <= =） */
const NUMBER_METHODS = [
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

/**
 * retrieval-filter 过滤字段定义（候选项由前端全量数据动态提供，见 getValueFn）。
 * 与旧版主机监控字段保持一致，但仅保留新版列表实际支持的过滤维度。
 */
export const HOST_FILTER_FIELDS: IFilterField[] = [
  {
    name: HOST_FILTER_FIELDS_ENUM.bkHostId,
    alias: window.i18n.t('主机'),
    type: EFieldType.text,
    methods: ENUM_METHODS,
    isEnableOptions: false,
  },
  {
    name: HOST_FILTER_FIELDS_ENUM.bkHostInnerIpV6,
    alias: window.i18n.t('内网IPv6'),
    type: EFieldType.text,
    methods: ENUM_METHODS,
    isEnableOptions: false,
  },
  {
    name: HOST_FILTER_FIELDS_ENUM.bkHostOuterIpV6,
    alias: window.i18n.t('外网IPv6'),
    type: EFieldType.text,
    methods: ENUM_METHODS,
    isEnableOptions: false,
  },
  {
    name: HOST_FILTER_FIELDS_ENUM.bkHostInnerIp,
    alias: window.i18n.t('内网IP'),
    type: EFieldType.text,
    methods: ENUM_METHODS,
    isEnableOptions: false,
  },
  {
    name: HOST_FILTER_FIELDS_ENUM.bkHostOuterIp,
    alias: window.i18n.t('外网IP'),
    type: EFieldType.text,
    methods: ENUM_METHODS,
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
    alias: window.i18n.t('OS名称'),
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
    type: EFieldType.keyword,
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
    type: EFieldType.integer,
    methods: NUMBER_METHODS,
    isEnableOptions: false,
  },
  {
    name: HOST_FILTER_FIELDS_ENUM.cpuLoad,
    alias: window.i18n.t('CPU五分钟负载'),
    type: EFieldType.integer,
    methods: NUMBER_METHODS,
    isEnableOptions: false,
  },
  {
    name: HOST_FILTER_FIELDS_ENUM.cpuUsage,
    alias: window.i18n.t('CPU使用率'),
    type: EFieldType.integer,
    methods: NUMBER_METHODS,
    isEnableOptions: false,
  },
  {
    name: HOST_FILTER_FIELDS_ENUM.diskInUse,
    alias: window.i18n.t('磁盘空间使用率'),
    type: EFieldType.integer,
    methods: NUMBER_METHODS,
    isEnableOptions: false,
  },
  {
    name: HOST_FILTER_FIELDS_ENUM.ioUtil,
    alias: window.i18n.t('磁盘IO使用率'),
    type: EFieldType.integer,
    methods: NUMBER_METHODS,
    isEnableOptions: false,
  },
  {
    name: HOST_FILTER_FIELDS_ENUM.memUsage,
    alias: window.i18n.t('应用内存使用率'),
    type: EFieldType.integer,
    methods: NUMBER_METHODS,
    isEnableOptions: false,
  },
  {
    name: HOST_FILTER_FIELDS_ENUM.pscMemUsage,
    alias: window.i18n.t('物理内存使用率'),
    type: EFieldType.integer,
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
