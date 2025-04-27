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
import type { TranslateResult } from 'vue-i18n';

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

/**
 * @description 事件检索 table表格列类型 枚举
 */
export enum ExploreTableColumnTypeEnum {
  /** 事件 -- 内容列 */
  CONTENT = 'content',
  /** 事件 -- 目标列 */
  LINK = 'link',
  /** 事件 -- 来源列 */
  PREFIX_ICON = 'prefix-icon',
  /** 事件 -- 名称列  */
  TEXT = 'text',
  /** 事件 -- 发生时间列 */
  TIME = 'time',
}

/**
 * @description 事件检索 事件来源 枚举
 */
export enum ExploreSourceTypeEnum {
  ALL = 'ALL',
  /** Kubernetes/BCS */
  BCS = 'BCS',
  /** BKCI/蓝盾 */
  BKCI = 'BKCI',
  /** 其他类型事件来源 */
  DEFAULT = 'DEFAULT',
  /** 系统/主机 */
  HOST = 'HOST',
}

/**
 * @description 事件type类型枚举
 */
export enum DimensionsTypeEnum {
  DEFAULT = 'Default',
  NORMAL = 'Normal',
  WARNING = 'Warning',
}

/** 检索表格列配置类型 */
export interface EventExploreTableColumn {
  /** 字段类型 */
  type?: ExploreTableColumnTypeEnum;
  /** 字段id */
  id: string;
  /** 字段名称（渲染指标列时为指标名称） */
  name: TranslateResult;
  /** 列宽 */
  width?: number;
  /** 最小列宽 */
  min_width?: number;
  /** 是否固定列 */
  fixed?: 'left' | 'right' | boolean;
  /** 自定义列表头类型 */
  customHeaderCls?: string;
  /** 自定义列表头内容 */
  renderHeader?: (column: EventExploreTableColumn) => any;
}

/** 事件检索 kv 面板跳转其他页面 类型枚举 */
export enum ExploreEntitiesTypeEnum {
  /** 主机 */
  HOST = 'ip',
  /** 容器 */
  K8S = 'k8s',
}

export type ExploreFieldMap = Record<string, Partial<IDimensionField> & { finalName?: string }>;
// /**
//  * @description 用于在表格 kv面板 中获取字段的类型s
//  * @description 将接口中的 fieldList 数组 结构转换为 kv 结构，从而提供使用 key 可以直接 get 方式取值，无需在循环
//  **/
// export interface ExploreFieldMap {
//   source: ExploreFieldTransform;
//   target: ExploreFieldTransform;
// }

export interface ExploreEntitiesItem {
  alias: string;
  dependent_fields?: string[];
  fields: string[];
  type: ExploreEntitiesTypeEnum;
}

/**
 * @description 用于判断在表格 kv面板 中字段是否为提供跳转功能
 * @description 将接口中的 entities 数组 结构转换为 kv 结构，从而提供使用 key 可以直接 get 方式取值，无需在循环
 **/
export type ExploreEntitiesMap = Record<string, ExploreEntitiesItem>;

export type ConditionChangeEvent = Pick<IWhereItem, 'key' | 'method'> & { value: string };

/**
 * @description 分词枚举
 */
export enum KVSplitEnum {
  /** 分词符号 */
  SEGMENTS = 'segments',
  /** 单词 */
  WORD = 'word',
}

export interface KVSplitItem {
  value: string;
  type: KVSplitEnum;
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
