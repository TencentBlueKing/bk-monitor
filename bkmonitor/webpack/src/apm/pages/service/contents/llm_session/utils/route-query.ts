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
import type { LlmViewMode } from '../typings';

/** 本 tab 需要在路由上保留的查询条件 */
export interface ILlmRouteState {
  keyword: string;
  /** 远程排序参数，最多一项：升序为字段名，降序加 - 前缀 */
  sort: string[];
  viewMode: LlmViewMode;
}

/** 把表格排序事件转成远程排序参数，order 为空表示取消排序 */
export function fromTableSort(prop: string, order: string): string[] {
  if (order === 'ascending') return [prop];
  if (order === 'descending') return [`-${prop}`];
  return [];
}

/** 同一个 key 在 URL 上出现多次时会被解析成数组，统一取最后一项并归一成字符串 */
function pickString(value: string | string[]): string {
  const val = Array.isArray(value) ? value[value.length - 1] : value;
  return typeof val === 'string' ? val : '';
}

/**
 * 解析路由参数。
 * 缺省或非法值一律回落到默认状态，避免手改 URL 后进入不可用的查询条件。
 */
export function readRouteQuery(query: Record<string, string | string[]> = {}): ILlmRouteState {
  const viewMode = pickString(query.llmViewMode);
  const sort = pickString(query.llmSort);
  return {
    viewMode: viewMode === 'trace' ? 'trace' : 'session',
    keyword: pickString(query.llmKeyword),
    sort: sort ? [sort] : [],
  };
}

/** 组装路由参数。空值置为 undefined，由路由层剔除，避免 URL 上堆积无意义的空参数 */
export function toRouteQuery(state: ILlmRouteState): Record<string, string> {
  return {
    llmViewMode: state.viewMode,
    llmKeyword: state.keyword || undefined,
    llmSort: state.sort[0] || undefined,
  };
}

/** 把远程排序参数反解成表格的 default-sort，用于还原表头的升降序箭头 */
export function toTableSort(sort: string[]): undefined | { order: string; prop: string } {
  const [field] = sort;
  if (!field) return undefined;
  return field.startsWith('-') ? { prop: field.slice(1), order: 'descending' } : { prop: field, order: 'ascending' };
}
