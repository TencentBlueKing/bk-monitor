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

export interface IApplicationItem {
  app_alias: string;
  app_name: string;
  application_id: number;
  metric_result_table_id: string;
  /** 是否置顶 */
  isTop?: boolean;
  [key: string]: any;
}

export type DimensionType = 'boolean' | 'date' | 'double' | 'integer' | 'keyword' | 'long' | 'object' | 'text';

export interface IDimensionOperation {
  alias: string;
  value: string;
  options: { label: string; name: string }[];
}

export interface IDimensionField {
  name: string;
  alias: string;
  type: DimensionType;
  is_option_enabled: boolean;
  is_dimensions: boolean;
  support_operations: IDimensionOperation[];
  pinyinStr?: string;
}

/** 维度列表树形结构 */
export interface IDimensionFieldTreeItem extends IDimensionField {
  count?: number;
  levelName?: string;
  expand?: boolean;
  children?: IDimensionFieldTreeItem[];
}

export interface ICommonParams {
  app_name: string;
  filters: any[];
  query_string: string;
  mode: 'span' | 'trace';
}

/** topk列表 */
export interface ITopKField {
  distinct_count: number;
  field: string;
  list: {
    alias: string;
    count: number;
    proportions: number;
    value: string;
  }[];
}

/** 统计信息 */
export interface IStatisticsInfo {
  field: string;
  total_count: number;
  field_count: number;
  distinct_count: number;
  field_percent: number;
  value_analysis?: {
    max: number;
    min: number;
    avg: number;
    median: number;
  };
}

export interface IStatisticsGraph {
  name: string;
  color: string;
  datapoints: number[];
  type: 'bar' | 'line';
  [key: string]: any;
}

type FieldMap = Record<string, Partial<IDimensionField>>;
/**
 * @description 用于在表格 列配置setting 中获取字段的类型
 * @description 将接口中的 fieldList 数组 结构转换为 kv 结构，从而提供使用 key 可以直接 get 方式取值，无需在循环
 **/
export type ExploreFieldMap = {
  trace: FieldMap;
  span: FieldMap;
};

export type ConditionChangeEvent = Pick<IWhereItem, 'key' | 'method'> & { value: string };

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
