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

import type { IWhereItem } from '../../components/retrieval-filter/utils';
import type { TranslateResult } from 'vue-i18n';

/**
 * @description 事件type类型枚举
 */
export enum DimensionsTypeEnum {
  DEFAULT = 'Default',
  NORMAL = 'Normal',
  WARNING = 'Warning',
}

/** 事件检索 kv 面板跳转其他页面 类型枚举 */
export enum ExploreEntitiesTypeEnum {
  /** 主机 */
  HOST = 'ip',
  /** 容器 */
  K8S = 'k8s',
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
 * @description 分词枚举
 */
export enum KVSplitEnum {
  /** 分词符号 */
  SEGMENTS = 'segments',
  /** 单词 */
  WORD = 'word',
}

export type ConditionChangeEvent = Pick<IWhereItem, 'key' | 'method'> & { value: string };

export type DimensionType = 'boolean' | 'date' | 'double' | 'integer' | 'keyword' | 'long' | 'object' | 'text';

/** 检索表格列配置类型 */
export interface EventExploreTableColumn {
  /** 自定义列表头类型 */
  customHeaderCls?: string;
  /** 是否固定列 */
  fixed?: 'left' | 'right' | boolean;
  /** 字段id */
  id: string;
  /** 最小列宽 */
  min_width?: number;
  /** 字段名称（渲染指标列时为指标名称） */
  name: TranslateResult;
  /** 是否可排序 */
  sortable?: boolean;
  /** 字段类型 */
  type?: ExploreTableColumnTypeEnum;
  /** 列宽 */
  width?: number;
  /** 自定义列表头内容 */
  renderHeader?: (column: EventExploreTableColumn) => any;
}

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

/**
 * @description 用于在表格 kv面板 中获取字段的类型
 * @description 将接口中的 fieldList 数组 结构转换为 kv 结构，从而提供使用 key 可以直接 get 方式取值，无需在循环
 **/
export interface ExploreFieldMap {
  source: ExploreFieldTransform;
  target: ExploreFieldTransform;
}

export type ExploreTableRequestParams = Omit<ExploreRequestParams, 'fields'>;

export type ExploreTotalRequestParams = Omit<ExploreRequestParams, 'fields' | 'limit' | 'offset'>;

export interface IDataIdItem {
  [key: string]: any;
  id: string;
  is_platform?: boolean;
  /** 是否置顶 */
  isTop?: boolean;
  name: string;
}

export interface IDimensionField {
  alias: string;
  is_dimensions: boolean;
  is_option_enabled: boolean;
  name: string;
  pinyinStr?: string;
  support_operations: IDimensionOperation[];
  type: DimensionType;
}
export interface IDimensionOperation {
  alias: string;
  options: { label: string; name: string }[];
  value: string;
}

export interface IFormData {
  data_source_label: string;
  data_type_label: string;
  filter_dict: Record<string, any>;
  group_by: any[];
  query_string: string;
  table: string;
  where: IWhereItem[];
}
/** 统计信息 */
export interface IStatisticsInfo {
  distinct_count: number;
  field: string;
  field_count: number;
  field_percent: number;
  total_count: number;
  value_analysis?: {
    avg: number;
    max: number;
    median: number;
    min: number;
  };
}

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

export interface ITopKRequestParams {
  app_name?: string;
  end_time: number;
  fields: string[];
  limit: number;
  query_configs: IFormData[];
  service_name?: string;
  start_time: number;
}

export interface KVSplitItem {
  type: KVSplitEnum;
  value: string;
}

type ExploreFieldTransform = Record<string, Partial<IDimensionField> & { finalName?: string }>;

interface ExploreRequestParams {
  app_name?: string;
  end_time: number;
  fields: string[];
  limit: number;
  offset: number;
  query_configs: IFormData[];
  service_name?: string;
  start_time: number;
}

export const EventExploreFeatures = [
  /** 收藏 */
  'favorite',
  /** 数据ID */
  'dataId',
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
