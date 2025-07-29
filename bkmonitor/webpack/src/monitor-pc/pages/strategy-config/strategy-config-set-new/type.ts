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

import type { MetricDetail } from './typings';

// 函数可选列表
export interface IFuncListItem {
  id: number;
  name: string;
  params: IFuncListParamsItem[];
}

export interface IFuncListParamsItem {
  default: number | string;
  list: Array<number | string>;
  name: string;
}

export interface IFuncLocalParamsItem {
  contenteditable: boolean;
  default: number | string;
  list: IIdNameItem[];
  name: string;
  parentId: number;
  value: number | string;
}

// 函数组件localValue
export interface IFuncLocalValue {
  id: number;
  name: string;
  params: IFuncLocalParamsItem[];
}

// 函数组件value
export interface IFuncValueItem {
  id: number;
  name: string;
  params: IIdNameItem[];
}

export interface IIdNameItem {
  id: number | string;
  name: number | string;
}
export const levelList: { id: number; name: string }[] = [
  {
    id: 1,
    name: window.i18n.tc('致命'),
  },
  {
    id: 2,
    name: window.i18n.tc('预警'),
  },
  {
    id: 3,
    name: window.i18n.tc('提醒'),
  },
];

export interface IActionConfig {
  id?: number;
  name?: string;
  plugin_id?: number;
  plugin_name?: string;
  plugin_type?: string;
}

// eslint-disable-next-line @typescript-eslint/naming-convention
export const noticeMethod = [
  {
    name: window.i18n.tc('基于分派规则通知'),
    value: 'by_rule',
  },
  {
    name: window.i18n.tc('默认通知'),
    value: 'only_notice',
  },
];

export interface IMultivariateAnomalyDetectionParams {
  metrics: MetricDetail[];
  refreshKey: string;
}
