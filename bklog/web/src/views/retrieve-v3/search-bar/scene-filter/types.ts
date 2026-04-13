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

/** 场景类型枚举 */
export enum SceneType {
  Container = 'container',
  Host = 'host',
  PaaS = 'paas',
  Service = 'service',
  Client = 'client',
  TRPC = 'trpc',
}

/** 筛选字段的输入组件类型 */
export type FilterInputType = 'select' | 'input';

/** select 数据来源类型 */
export type SelectSourceType = 'static' | 'api';

/** select 静态选项 */
export interface SelectOption {
  id: string;
  name: string;
}

/** 筛选字段配置 */
export interface FilterFieldConfig {
  /** 显示标签 */
  label: string;
  /** 是否跳过国际化翻译（纯英文专有名词标记为 true） */
  skipI18n?: boolean;
  /** 字段名 */
  fieldName: string;
  /** 字段数据类型 */
  fieldType: 'string' | 'integer';
  /** 输入组件类型 */
  inputType: FilterInputType;
  /** select 数据来源（仅 inputType 为 select 时有效） */
  sourceType?: SelectSourceType;
  /** 静态选项列表（仅 sourceType 为 static 时有效） */
  staticOptions?: SelectOption[];
  /** API 请求方法（仅 sourceType 为 api 时有效），后续扩展 */
  apiFetcher?: () => Promise<SelectOption[]>;
  /** 是否支持多选（仅 inputType 为 select 时有效） */
  multiple?: boolean;
  /** 是否可搜索 */
  searchable?: boolean;
  /** placeholder */
  placeholder?: string;
}

/** 每场景的显示字段配置：key = SceneType, value = 有序 fieldName 数组（null 表示全部显示、默认顺序） */
export type SceneDisplayFields = Record<string, string[] | null>;

/** 场景配置 */
export interface SceneConfig {
  /** 场景类型 */
  type: SceneType;
  /** 场景显示名称 */
  label: string;
  /** 是否跳过国际化翻译（纯英文专有名词标记为 true） */
  skipI18n?: boolean;
  /** 场景图标 */
  icon: string;
  /** 筛选字段列表 */
  fields: FilterFieldConfig[];
}

/** 筛选条件值 */
export type FilterValues = Record<string, string | string[] | number | number[]>;
