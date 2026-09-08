/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
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

import type { DimensionType } from '../../trace-explore/typing';
import type { RumFieldDisplayType } from './enum';

export type { DimensionType };

/**
 * 归一化后的字段结构。
 *
 * 字段名刻意与 trace 检索的维度字段保持一致（name / alias / type / is_dimensions /
 * can_displayed / supported_operations），以便直接复用 FieldTypeIcon、convertToTree、
 * StatisticsList、ExploreFieldSetting 等既有组件而不需要再写适配层。
 */
export interface IRumField {
  alias: string;
  /** 是否可作为表格列展示，源自 is_list */
  can_displayed: boolean;
  /** 字段展示类型（仅特殊渲染字段有值） */
  field_display_type?: RumFieldDisplayType;
  field_unit: string;
  /** 是否支持聚合统计，决定能否做统计分析，源自 is_agg */
  is_dimensions: boolean;
  /** 是否为数据中真实存在的字段，「原始字段」分组据此聚合 */
  is_real: boolean;
  /** 是否可检索，源自 is_searchable */
  is_searched: boolean;
  name: string;
  option_values: IRumFieldOptionValue[];
  /** 别名与字段名的拼音，供左侧栏搜索匹配 */
  pinyinStr: string;
  supported_operations: IRumFieldOperation[];
  type: DimensionType;
}

/** 归一化后的字段分组 */
export interface IRumFieldGroup {
  alias: string;
  fields: IRumField[];
  name: string;
  /** 适用的 span 类型，为空数组表示所有类型都适用 */
  supported_span_types: string[];
}

/** 字段支持的操作符 */
export interface IRumFieldOperation {
  label: string;
  operator: string;
  placeholder?: string;
  wildcard_operator?: string;
}

/** 字段的预设枚举值，有别名时 UI 展示为 `alias(value)` */
export interface IRumFieldOptionValue {
  alias?: string;
  value: string;
}

/** view_config 接口返回的原始字段结构 */
export interface IRumRawField {
  field_alias: string;
  field_display_type?: RumFieldDisplayType;
  field_name: string;
  field_type: DimensionType;
  field_unit?: string;
  is_agg: boolean;
  is_list: boolean;
  is_real: boolean;
  is_searchable: boolean;
  option_values?: IRumFieldOptionValue[];
  supported_operations?: IRumFieldOperation[];
}

/** view_config 接口返回的原始分组结构 */
export interface IRumRawGroup {
  alias: string;
  field_names: string[];
  name: string;
  supported_span_types?: string[];
}

/** view_config 接口原始响应 */
export interface IRumRawViewConfig {
  default_sort: string[];
  display_fields: string[];
  fields: IRumRawField[];
  groups: IRumRawGroup[];
  span_type_display_fields?: Record<string, string[]>;
}

/** 归一化后的视图配置 */
export interface IRumViewConfig {
  default_sort: string[];
  display_fields: string[];
  fields: IRumField[];
  groups: IRumFieldGroup[];
  /** key 为 span 类型，value 为该类型下默认展示的字段名列表 */
  span_type_display_fields: Record<string, string[]>;
}
