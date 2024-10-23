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
export interface IServiceConfig {
  value: string;
  text: string;
  label: string;
  name: string;
  operate: number;
  values: string[];
  value_type: number;
  checked?: boolean;
}
export interface IColumn {
  label: string;
  prop: string;
}

export interface IDataItem {
  [key: string]: string;
}
export interface IFilterCondition {
  key: string;
  method: string;
  value: string[];
  condition: string;
}

export interface IFilterType {
  call_filter: IFilterCondition[];
  group_by_filter: IDataItem[];
  time_shift: IDataItem[];
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

export interface IListItem {
  value?: string;
  text?: string;
}

export type CallOptions = {
  server: string;
  group_by: string[];
  method: string;
  limit: number;
  metric_cal_type: string;
  // 时间对比 字段
  time_shift: {
    start_time: number;
    end_time: number;
    alias: string;
  }[];
  // 左侧查询条件字段
  call_filter: IFilterCondition[];
} & Record<string, string>;

export type IFilterData = {
  caller: IFilterCondition[];
  callee: IFilterCondition[];
};
