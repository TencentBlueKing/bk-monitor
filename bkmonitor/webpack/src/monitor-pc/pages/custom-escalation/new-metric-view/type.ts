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
export interface IObjItem {
  [key: string]: any;
}
export interface IDimensionItem {
  name: string;
  key: string;
  checked?: boolean;
  value?: number | string;
  text?: string;
}

export interface IColumnItem {
  label: string;
  prop: string;
  width?: number | undefined;
  sortable?: boolean | undefined;
  renderFn?: (row) => void;
  fixed?: string;
}
export interface IDataItem {
  name?: string;
  value?: number;
  min?: number;
  max?: number;
  color?: string;
  avg?: number;
  latest?: number;
  percentage?: number;
  compare_values?: {
    value?: number;
    offset?: string;
    fluctuation?: number;
  }[];
  dimensions?: IObjItem;
}

export interface IRefreshItem {
  // 刷新间隔名称
  name: string;
  // 自动刷新间隔值
  id: number | string;
}

export interface IGroupBy {
  field: string;
  split: boolean;
}

export interface ILimit {
  function: 'bottom' | 'top';
  limit: number;
}

export interface ICondition {
  key: string;
  method: 'eq' | 'exclude' | 'include' | 'neq' | 'nreg' | 'reg';
  value: string[];
  condition?: 'and' | 'or'; // 可选字段
}

export interface ICommonCondition {
  key: string;
  method: 'eq' | 'exclude' | 'include' | 'neq' | 'nreg' | 'reg';
  value: string[];
}

export interface ICompare {
  type: 'metric' | 'time';
  offset: string[]; // 用于描述对比的时间偏移
}

export interface IMetricAnalysisConfig {
  bk_biz_id: number;
  time_series_group_id: number;
  metrics: string[];
  group_by: IGroupBy[];
  limit: ILimit;
  conditions: ICondition[];
  common_conditions: ICommonCondition[];
  compare: ICompare;
  start_time: number;
  end_time: number;
  show_statistical_value: boolean;
  highlight_peak_value?: boolean;
  view_column?: number;
}
export interface IFilterConfig {
  group_by: string[];
  function: {
    time_compare: string[];
  };
}

export interface IResultItem {
  metrics: string[];
  where: {
    key: string;
    method: string;
    condition: string;
    value: string[];
  }[];
  common_conditions: {
    key: string;
    method: string;
    value: string[];
  }[];
  group_by: {
    field: string;
    split: boolean;
  }[];
  limit: {
    function: 'bottom' | 'top';
    limit: number;
  };
  compare: {
    type: string;
    offset: string[];
  };
  show_statistical_value: boolean;
  highlight_peak_value: boolean;
  view_column: number;
}
