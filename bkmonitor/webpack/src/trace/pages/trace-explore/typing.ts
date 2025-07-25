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

import type { IWhereItem } from '../../components/retrieval-filter/typing';

export type ConditionChangeEvent = Pick<IWhereItem, 'key' | 'method'> & { value: string };

export type DimensionType = 'boolean' | 'date' | 'double' | 'integer' | 'keyword' | 'long' | 'object' | 'text';

export type ExploreFieldList = {
  span: IDimensionField[];
  trace: IDimensionField[];
};

export interface IApplicationItem {
  [key: string]: any;
  app_alias: string;
  app_name: string;
  application_id: number;
  /** 是否置顶 */
  isTop?: boolean;
  metric_result_table_id: string;
}

export interface ICommonParams {
  app_name: string;
  filters: any[];
  mode: 'span' | 'trace';
  query_string: string;
}

export interface IDimensionField {
  alias: string;
  can_displayed: boolean;
  is_dimensions: boolean;
  is_option_enabled: boolean;
  name: string;
  pinyinStr?: string;
  support_operations: IDimensionOperation[];
  type: DimensionType;
}

/** 维度列表树形结构 */
export interface IDimensionFieldTreeItem extends IDimensionField {
  children?: IDimensionFieldTreeItem[];
  count?: number;
  expand?: boolean;
  levelName?: string;
}

export interface IDimensionOperation {
  alias: string;
  options: { label: string; name: string }[];
  value: string;
}

export interface IStatisticsGraph {
  [key: string]: any;
  color: string;
  datapoints: [number, number | string][];
  name: string;
  type: 'bar' | 'line';
}

/** 统计信息 */
export interface IStatisticsInfo {
  distinct_count: number;
  field: string;
  field_count: number;
  field_percent: number;
  total_count: number;
  value_analysis?: {
    avg: number | string;
    max: number | string;
    median: number | string;
    min: number | string;
  };
}

/** topk列表 */
export interface ITopKField {
  distinct_count: number;
  field: string;
  list: {
    alias?: string;
    count: number;
    proportions: number;
    value: string;
  }[];
}

export const EventExploreFeatures = [
  /** 收藏 */
  'favorite',
  /** 应用 */
  'application',
  /** 时间范围 */
  'dateRange',
  /** 维度筛选 */
  'dimensionFilter',
  /** 标题 */
  'title',
  /** 表头 */
  'header',
] as const;

export type HideFeatures = Array<(typeof EventExploreFeatures)[number]>;
