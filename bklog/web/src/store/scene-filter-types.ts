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

/** 场景类型枚举（值对应接口返回的 id） */
/* eslint-disable no-unused-vars */
export enum SceneType {
  Container = 'k8s',
  Host = 'host',
  PaaS = 'bk_paas',
  Service = 'apm',
}

/** ============ 接口返回数据类型 ============ */

/** 接口返回的维度字段（字段名与 API 返回 JSON 保持一致） */
export interface SceneDimensionItem {
  /** 字段 key，提交请求时传递 */
  key: string;
  /** 显示名称 */
  name: string;
  /** 是否必填 */
  required: boolean;
  /** 字段数据类型 */
  type: 'string' | 'integer';
  /** 是否支持多选 */
  multiple?: boolean;
  /** 支持的操作符列表 */
  ops: string[];
  /** 选项类型：static 前端直接渲染 choices，dynamic 调用 dimension_values 拉取，free_input 自由输入 */
  choices_type?: 'static' | 'dynamic' | 'free_input';
  /** 静态候选值列表（仅 choices_type=static 时存在） */
  choices?: Array<{ id: string; name: string }>;
}

/** 接口返回的场景配置项 */
export interface SceneConfigItem {
  /** 场景 ID */
  id: string;
  /** 场景显示名称 */
  name: string;
  /** 维度字段列表 */
  dimensions: SceneDimensionItem[];
}

/** ============ 维度值预览接口类型 ============ */

/** 维度值预览请求参数 */
export interface SceneDimensionValuesRequest {
  /** 业务 ID */
  bkBizId: number;
  /** 场景标识，如 "k8s" */
  scene: string;
  /** 要查询的维度 key */
  dimensionKey: string;
  /** 前置级联筛选条件 */
  filters?: Record<string, string>;
}

/** 维度值预览响应 */
export interface SceneDimensionValuesResponse {
  /** 查询的维度 key（回显） */
  dimensionKey: string;
  /** 该维度下去重后的所有可选值 */
  values: string[];
}

/** ============ 组件内部使用类型 ============ */

/** 筛选字段配置（从接口 dimension 转换而来） */
export interface FilterFieldConfig {
  /** 显示名称（对应接口 dimension.name） */
  name: string;
  /** 字段 key（对应接口 dimension.key） */
  key: string;
  /** 字段数据类型 */
  fieldType: 'string' | 'integer';
  /** 选项类型：static 前端直接渲染 choices，dynamic 调用 dimension_values 拉取，free_input 自由输入 */
  choicesType?: 'static' | 'dynamic' | 'free_input';
  /** 静态候选值列表（仅 choicesType=static 时有效） */
  choices?: Array<{ id: string; name: string }>;
  /** 是否必填 */
  required?: boolean;
  /** 支持的操作符列表 */
  ops?: string[];
  /** 是否支持多选 */
  multiple?: boolean;
  /** 是否可搜索 */
  searchable?: boolean;
  /** placeholder */
  placeholder?: string;
}

/** 单个字段的筛选值（含操作符） */
export interface FilterFieldValue {
  /** 操作符 key，如 'eq'、'ne'、'req'、'nreq' */
  op: string;
  /** 字段值 */
  value: string | string[] | number | number[];
}

/** 每场景的显示字段配置 */
/** 新: { scene: [[field, op], [field, op]] }，null 表示全部显示、默认顺序 */
export type SceneDisplayFields = Record<string, Array<[string, string]> | null>;

/** 场景配置（从接口数据 + 本地映射合并而来） */
export interface SceneConfig {
  /** 场景类型（对应接口 id / SceneType 枚举值） */
  type: string;
  /** 场景显示名称（从本地映射获取） */
  label: string;
  /** 是否跳过国际化翻译 */
  skipI18n?: boolean;
  /** 场景图标（从本地映射获取） */
  icon: string;
  /** 筛选字段列表 */
  fields: FilterFieldConfig[];
  /** 是否禁用（接口未返回该场景配置时为 true，按钮置灰展示） */
  disabled?: boolean;
}

/** 筛选条件值（含操作符） */
export type FilterValues = Record<string, FilterFieldValue>;
