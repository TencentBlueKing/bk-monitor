/*
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
export const CALLER_CALLEE_TYPE = [
  {
    label: '主调',
    id: 'caller',
  },
  {
    label: '被调',
    id: 'callee',
  },
];

export const PERSPECTIVE_TYPE = [
  {
    label: '单视角',
    id: 'single',
  },
  {
    label: '多视角',
    id: 'multiple',
  },
];

export const CHART_TYPE = [
  {
    label: '饼图',
    id: 'caller-pie-chart',
  },
  {
    label: '柱状图',
    id: 'apm-timeseries-chart',
  },
];

export const TAB_TABLE_REQUEST_COLUMN = [
  {
    label: '数值',
    prop: 'request',
  },
  {
    label: '占比',
    prop: 'proportion',
  },
];
export const TAB_TABLE_TIMEOUT_COLUMN = [
  {
    label: '成功率',
    prop: 'successRate',
  },
  {
    label: '超时率',
    prop: 'timeoutRate',
  },
  {
    label: '异常率',
    prop: 'errorRate',
  },
];
export const TAB_TABLE_CONSUMING_COLUMN = [
  {
    label: 'AVG',
    prop: 'avg',
  },
  {
    label: 'P50',
    prop: 'p50',
  },
  {
    label: 'P95',
    prop: 'P95',
  },
  {
    label: 'P99',
    prop: 'P99',
  },
];

export const TAB_TABLE_TYPE = [
  {
    label: '请求量',
    id: 'request',
    columns: TAB_TABLE_REQUEST_COLUMN,
    icon: 'icon-bingtu',
  },
  {
    label: '成功异常超时率',
    id: 'timeout',
    columns: TAB_TABLE_TIMEOUT_COLUMN,
  },
  {
    label: '耗时(ms)',
    id: 'consuming',
    columns: TAB_TABLE_CONSUMING_COLUMN,
  },
];

export const LIMIT_TYPE_LIST = [
  { id: 1, name: '请求量' },
  { id: 2, name: '成功率（%）' },
  { id: 3, name: '异常率（%）' },
  { id: 4, name: '超时率（%）' },
  { id: 5, name: '平均耗时(ms)' },
];

export const SYMBOL_LIST = [
  {
    value: 'eq',
    label: '等于',
  },
  {
    value: 'neq',
    label: '不等于',
  },
  {
    value: 'before_req',
    label: '前匹配',
  },
  {
    value: 'after_req',
    label: '后匹配',
  },
  {
    value: 'include',
    label: '包含',
  },
  {
    value: 'exclude',
    label: '不包含',
  },
  {
    value: 'reg',
    label: '正则',
  },
];
