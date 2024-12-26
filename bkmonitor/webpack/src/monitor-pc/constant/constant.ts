/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
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
export const PERFORMANCE_CHART_TYPE = '__chart_view_type__'; // 主机视图图表显示类型 localstorage key值
export const COLLECT_CHART_TYPE = '__chart_view_type__'; // 采集视图图表显示类型 localstorage key值
export const DATARETRIEVAL_CHART_TYPE = '__chart_view_type__'; // 数据检索视图图表显示类型 localstorage key值
// 仪表盘页面缓存各业务的仪表盘默认显示 localstorage key值 string | {[业务id]: [仪表盘id]}
export const DASHBOARD_ID_KEY = '___grafana_dashboard_id_v3___'.toLocaleUpperCase();
export const UPDATE_GRAFANA_KEY = '___grafana_update_key_v1___'.toLocaleUpperCase();
/** 阈值方法列表 */
export const THRESHOLD_METHOD_LIST = [
  { id: 'eq', name: '=' },
  { id: 'gt', name: '>' },
  { id: 'gte', name: '>=' },
  { id: 'lt', name: '<' },
  { id: 'lte', name: '<=' },
  { id: 'neq', name: '!=' },
];
// 监控条件方法列表
export const CONDITION_METHOD_LIST = [
  { id: 'eq', name: '=' },
  { id: 'gt', name: '>' },
  { id: 'gte', name: '>=' },
  { id: 'lt', name: '<' },
  { id: 'lte', name: '<=' },
  { id: 'neq', name: '!=' },
  { id: 'include', name: 'include' },
  { id: 'exclude', name: 'exclude' },
  { id: 'reg', name: 'regex' },
  { id: 'nreg', name: 'nregex' },
];
export const NUMBER_CONDITION_METHOD_LIST = [
  { id: 'eq', name: '=' },
  { id: 'gt', name: '>' },
  { id: 'gte', name: '>=' },
  { id: 'lt', name: '<' },
  { id: 'lte', name: '<=' },
  { id: 'neq', name: '!=' },
  { id: 'include', name: 'include' },
  { id: 'exclude', name: 'exclude' },
  { id: 'reg', name: 'regex' },
  { id: 'nreg', name: 'nregex' },
];
export const LOG_CONDITION_METHOD_LIST = [
  { id: 'is', name: 'is' },
  { id: 'is one of', name: 'is one of' },
  { id: 'is not', name: 'is not' },
  { id: 'is not one of', name: 'is not one of' },
];
export const STRING_CONDITION_METHOD_LIST = [
  { id: 'eq', name: '=' },
  { id: 'neq', name: '!=' },
  { id: 'include', name: 'include' },
  { id: 'exclude', name: 'exclude' },
  { id: 'reg', name: 'regex' },
  { id: 'nreg', name: 'nregex' },
];
export const SIMPLE_METHOD_LIST = [
  {
    id: 'gt',
    name: '>',
  },
  {
    id: 'gte',
    name: '>=',
  },
  {
    id: 'lt',
    name: '<',
  },
  {
    id: 'lte',
    name: '<=',
  },
  {
    id: 'eq',
    name: '=',
  },
];

export const CONDITION = [
  { id: 'or', name: 'OR' },
  { id: 'and', name: 'AND' },
];

export const METHOD_LIST = [
  {
    id: 'SUM',
    name: 'SUM',
  },
  {
    id: 'AVG',
    name: 'AVG',
  },
  {
    id: 'MAX',
    name: 'MAX',
  },
  {
    id: 'MIN',
    name: 'MIN',
  },
  {
    id: 'COUNT',
    name: 'COUNT',
  },
];

export const CP_METHOD_LIST = [
  {
    id: 'CP50',
    name: 'P50',
  },
  {
    id: 'CP90',
    name: 'P90',
  },
  {
    id: 'CP95',
    name: 'P95',
  },
  {
    id: 'CP99',
    name: 'P99',
  },
  {
    id: 'sum_without_time',
    name: 'SUM(PromQL)',
  },
  {
    id: 'max_without_time',
    name: 'MAX(PromQL)',
  },
  {
    id: 'min_without_time',
    name: 'MIN(PromQL)',
  },
  {
    id: 'count_without_time',
    name: 'COUNT(PromQL)',
  },
  {
    id: 'avg_without_time',
    name: 'AVG(PromQL)',
  },
];
export const K8S_METHOD_LIST = [
  {
    id: 'sum',
    name: 'SUM(PromQL)',
  },
  {
    id: 'max',
    name: 'MAX(PromQL)',
  },
  {
    id: 'min',
    name: 'MIN(PromQL)',
  },
  {
    id: 'count',
    name: 'COUNT(PromQL)',
  },
  {
    id: 'avg',
    name: 'AVG(PromQL)',
  },
];
export const INTERVAL_LIST = [
  {
    id: 60,
    name: '1',
  },
  {
    id: 120,
    name: '2',
  },
  {
    id: 300,
    name: '5',
  },
  {
    id: 600,
    name: '10',
  },
  {
    id: 900,
    name: '15',
  },
  {
    id: 1200,
    name: '20',
  },
];

export const CHART_INTERVAL = [
  {
    id: 'auto',
    name: 'Auto',
  },
  {
    id: 60,
    name: '1 min',
  },
  {
    id: 5 * 60,
    name: '5 min',
  },
  {
    id: 60 * 60,
    name: '1 h',
  },
  {
    id: 24 * 60 * 60,
    name: '1 d',
  },
];

/** IPv4 正则匹配规则 */
export const IPV4 =
  /((\d|[1-9]\d|1\d\d|2[0-4]\d|25[0-5])\.){3}(\d|[1-9]\d|1\d\d|2[0-4]\d|25[0-5])(?::(?:[0-9]|[1-9][0-9]{1,3}|[1-5][0-9]{4}|6[0-4][0-9]{3}|65[0-4][0-9]{2}|655[0-2][0-9]|6553[0-5]))?/;

export const NO_BUSSINESS_PAGE_HASH = 'NO_BUSSINESS_PAGE_HASH';
export const PANEL_INTERVAL_LIST = [
  {
    name: 'auto',
    id: 'auto',
  },
  {
    name: window.i18n.tc('10 秒'),
    id: '10s',
  },
  {
    name: window.i18n.tc('30 秒'),
    id: '30s',
  },
  {
    name: window.i18n.tc('60 秒'),
    id: '60s',
  },
  {
    name: window.i18n.tc('2 分钟'),
    id: '2m',
  },
  {
    name: window.i18n.tc('5 分钟'),
    id: '5m',
  },
  {
    name: window.i18n.tc('10 分钟'),
    id: '10m',
  },
  {
    name: window.i18n.tc('30 分钟'),
    id: '30m',
  },
  {
    name: window.i18n.tc('1 小时'),
    id: '1h',
  },
];

export const TARGET_TABEL_EXPAND_MAX = 5; /** 采集下发目标默认最大展开表格数量 */

export const LETTERS = 'abcdefghijklmnopqrstuvwxyz';
