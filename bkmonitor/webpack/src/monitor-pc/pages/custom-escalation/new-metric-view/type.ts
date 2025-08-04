export interface IColumnItem {
  colKey?: string;
  color?: string;
  field?: string;
  fixed?: string;
  items?: IDataItem[];
  key?: string;
  label?: string | undefined;
  minWidth?: number | string;
  name?: string;
  prop?: string;
  sortable?: boolean | undefined;
  sortBy?: string;
  sorter?: boolean;
  sortType?: string;
  title?: Function | string;
  width?: number | string;
  renderFn?: (row) => void;
}
export interface ICommonCondition {
  key: string;
  method: 'eq' | 'exclude' | 'include' | 'neq' | 'nreg' | 'reg';
  value: string[];
}

export interface ICompare {
  offset: string[]; // 用于描述对比的时间偏移
  type: '' | 'metric' | 'time';
}
export interface ICondition {
  condition?: 'and' | 'or'; // 可选字段
  key: string;
  method: 'eq' | 'exclude' | 'include' | 'neq' | 'nreg' | 'reg';
  value: string[];
}

export interface IDataItem {
  avg?: number;
  color?: string;
  dimensions?: IObjItem;
  latest?: number;
  max?: number;
  min?: number;
  name?: string;
  percentage?: number;
  show?: boolean;
  target?: string;
  time_offset?: string;
  timeOffset?: string;
  unit?: string;
  value?: number;
  compare_values?: {
    fluctuation?: number;
    offset?: string;
    value?: number;
  }[];
}

export interface IDimensionItem {
  alias?: string;
  checked?: boolean;
  key: string;
  name: string;
  text?: string;
  value?: number | string;
}

export interface IFilterConfig {
  group_by: string[];
  function: {
    time_compare: string[];
  };
}

export interface IGroupBy {
  field: string;
  split: boolean;
}

export interface ILimit {
  function: 'bottom' | 'top';
  limit: number;
}

export interface IMetricAnalysisConfig {
  bk_biz_id: number;
  common_conditions: ICommonCondition[];
  compare: ICompare;
  conditions: ICondition[];
  end_time: number;
  group_by: IGroupBy[];
  highlight_peak_value?: boolean;
  limit: ILimit;
  metrics: string[];
  show_statistical_value: boolean;
  start_time: number;
  time_series_group_id: number;
  view_column?: number;
}

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
export interface IRefreshItem {
  // 自动刷新间隔值
  id: number | string;
  // 刷新间隔名称
  name: string;
}

export interface IResultItem {
  highlight_peak_value: boolean;
  metrics: string[];
  show_statistical_value: boolean;
  view_column: number;
  common_conditions: {
    key: string;
    method: string;
    value: string[];
  }[];
  compare: {
    offset: string[];
    type: string;
  };
  group_by: {
    field: string;
    split: boolean;
  }[];
  limit: {
    function: 'bottom' | 'top';
    limit: number;
  };
  where: {
    condition: string;
    key: string;
    method: string;
    value: string[];
  }[];
}

export interface ITableColumn {
  $index: number;
  checked?: boolean;
  // 常驻列 不可取消勾选列
  disabled?: boolean;
  // 是否固定列 left | right
  fixed?: 'left' | 'right';
  // 字段id
  id: string;
  // 最大列宽 必须配合自定义calcColumnWidth方法使用
  max_width?: number;
  // 最小列宽
  min_width?: number;
  // 字段名称
  name: string;
  // 其他属性
  props?: Record<string, any>;
  // 是否伸缩大小
  resizable?: boolean;
  // 是否需要溢出提示
  showOverflowTooltip?: boolean;
  // 是否可以排序
  sortable?: 'custom' | boolean;
  // 列宽
  width?: number;
  // renderHeader
  renderHeader?: () => any;
}
