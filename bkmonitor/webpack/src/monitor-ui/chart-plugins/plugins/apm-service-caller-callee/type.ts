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
import type { ETypeSelect as EGroupCompareType } from 'monitor-pc/pages/monitor-k8s/components/group-compare-select/utils';
/* 主调/被调 */
export enum EKind {
  callee = 'callee',
  caller = 'caller',
}
/* 头部对比/group by 切换 */
export enum EParamsMode {
  contrast = 'contrast',
  group = 'group',
}

/* 头部对比时间预设 */
export enum EPreDateType {
  lastWeek = '1w',
  yesterday = '1d',
}
export type CallOptions = {
  [key: string]: any;
  // 左侧查询条件字段
  call_filter: IFilterCondition[];
  group_by: string[];
  limit: number;
  method: string;
  metric_cal_type: string;
  // 时间对比 字段
  time_shift: string[];
  // 对比 还是 group by
  tool_mode: EGroupCompareType;
};
export type DimensionItem = {
  active: boolean;
  text: string;
  value: string;
};
export type IChartOption = {
  dimensions?: IDataItem;
  interval?: number;
  name?: string;
  time?: string;
};
export interface IColumn {
  label: string;
  prop: string;
}
export interface IDataItem {
  [key: string]: any;
  dimensions?: Record<string, any>;
}
export type IDimensionChartOpt = {
  dimensionTime?: IDataItem;
  drillFilterData?: IDataItem[];
  drillGroupBy?: string[];
  metric_cal_type: string;
  metric_cal_type_name: string;
  time_shift: string;
};

export interface IFilterCondition {
  condition: string;
  key: string;
  method: string;
  value: string[];
}

export type IFilterData = {
  callee: IColumn[];
  caller: IColumn[];
};
export interface IFilterOption extends IFilterCondition {
  loading: boolean;
  options: { text: string; value: string }[];
}
export interface IFilterType {
  call_filter: IFilterCondition[];
  group_by_filter: IDataItem[];
  time_shift: IDataItem[];
}
export interface IListItem {
  label?: string;
  text?: string;
  value?: string;
}

export type IPointTime = {
  endTime?: number;
  startTime?: number;
};

export interface IServiceConfig {
  checked?: boolean;
  label: string;
  name: string;
  operate: number;
  text: string;
  value: string;
  value_type: number;
  values: string[];
}
export interface ITabItem {
  icon?: string;
  id: string;
  label: string;
  handle?: () => void;
}
