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

export interface IFormData {
  data_source_label: string;
  data_type_label: string;
  table: string;
  query_string: string;
  where?: IWhereItem[];
  group_by?: any[];
  filter_dict?: Record<string, any>;
}

export interface IDataIdItem {
  name: string;
  id: string;
}

export type DimensionType = 'date' | 'interger' | 'keyword' | 'text';

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
}

export interface ITopKRequestParams {
  limit: number;
  query_configs: IFormData[];
  fields: string[];
  start_time: number;
  end_time: number;
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
  /** Kubernetes/BCS */
  BCS = 'BCS',
  /** CICD/蓝盾 */
  CICD = 'CICD',
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
  type: ExploreTableColumnTypeEnum;
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
}

export enum EventExploreEntitiesType {
  /** 主机 */
  HOST = 'ip',
  /** 容器 */
  K8S = 'k8s',
}

export interface EventExploreTableRequestConfigs {
  apiModule: string;
  apiFunc: string;
  data: Record<string, any>;
}
