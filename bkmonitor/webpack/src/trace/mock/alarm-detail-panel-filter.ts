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

/**
 * 【临时联调 mock，联调就绪后请删除本文件 + panel-trace、panel-event 里的 filterRowsByPanelFilterMock 调用】
 *
 * 告警详情 - 调用链 / 关联事件 tab 的筛选条件与数据源下拉的前端验证开关。
 *
 * 背景：`fta/alert/v2/alert/traces/` 与 `fta/alert/v2/alert/events/` 目前只接受
 * alert_id / limit / offset / sources，还不认识 filters / where / query_string，
 * 也不认识用来切换数据源的 app_name / table，所以前端把这些参数传上去都不会生效。
 * 开着本 mock 时，在拿到接口返回后按同样的条件在前端过滤一遍（见
 * filterRowsByPanelFilterMock），并把切换数据源表达成空结果（见 filterRowsBySourceMock），
 * 用来验证这两条交互链路。
 *
 * 触发方式（hash 或 search 均可）：`panelFilterMock=1`
 * 例：`?bizId=2&panelFilterMock=1#/event-center/detail/xxx`
 *
 * 已知偏差（后端补齐参数后即消失）：
 *   - 只过滤「当前已拉到的这一页」，不会重新向后端要更多数据，所以过滤后条数会偏少；
 *   - 触底加载仍按原始分页走，滚动到底部拿到的下一页同样只做前端过滤。
 */
import { EMode } from '../components/retrieval-filter/typing';

import type { IWhereItem } from '../components/retrieval-filter/typing';

/** 把一行数据里的某个字段取成可比较的值 */
type TFieldValueGetter<T> = (row: T, key: string) => unknown;

const NOT_METHODS = ['not_equal', 'ne', 'exclude', 'not_like', 'not contains match phrase', 'not exists'];
const EXISTS_METHODS = ['exists', 'not exists'];
const EQUAL_METHODS = ['equal', 'eq', 'not_equal', 'ne'];
const QUERY_STRING_KEYWORDS = ['AND', 'OR', 'NOT', 'and', 'or', 'not'];

let cachedOn: boolean | null = null;

/**
 * 在前端按筛选条件过滤接口返回的列表。mock 未开启时原样返回。
 * @param rows 接口返回的当前页数据
 * @param options.getFieldValue 从一行数据里取某个字段值
 * @param options.getAllValues 取一行数据的全部可检索值，用于全文（`*`）与语句模式
 */
export function filterRowsByPanelFilterMock<T>(
  rows: T[],
  options: {
    filterMode: EMode;
    getAllValues: (row: T) => unknown[];
    getFieldValue: TFieldValueGetter<T>;
    queryString: string;
    where: IWhereItem[];
  }
): T[] {
  if (!isPanelFilterMockOn() || !rows?.length) return rows;
  const { filterMode, where, queryString, getFieldValue, getAllValues } = options;

  if (filterMode === EMode.queryString) {
    if (!queryString?.trim()) return rows;
    return rows.filter(row => matchQueryString(toComparableList(getAllValues(row)), queryString));
  }

  if (!where?.length) return rows;
  return rows.filter(row => {
    const allValues = toComparableList(getAllValues(row));
    return where.every(item => matchWhereItem(row, item, getFieldValue, allValues));
  });
}

/**
 * 模拟「切换应用 / 数据ID」。
 *
 * 接口只按告警自身关联的数据源返回，前端拿不到别的应用或数据ID 下的数据，
 * 所以这里把「换了数据源」表达成空结果：切走后表格转空态，切回来数据恢复，
 * 用来验证下拉切换 → 清空筛选 → 重新查询 → 表格刷新这条链路。
 *
 * @param isOriginSource 当前选中的是否就是告警自身关联的那个数据源
 */
export function filterRowsBySourceMock<T>(rows: T[], isOriginSource: boolean): T[] {
  if (!isPanelFilterMockOn() || isOriginSource) return rows;
  return [];
}

export function isPanelFilterMockOn(): boolean {
  return readPanelFilterMockFlag();
}

function matchOne(rowValues: string[], targetValue: string, method: string): boolean {
  const target = targetValue.toLocaleLowerCase();
  if (EQUAL_METHODS.includes(method)) {
    return rowValues.some(value => value.toLocaleLowerCase() === target);
  }
  return rowValues.some(value => value.toLocaleLowerCase().includes(target));
}

/**
 * 语句模式只做很粗的兜底：把语句里出现的字面量当关键字，命中任意一个字段值就算通过。
 * 真实的 query_string 解析在后端，这里只为了让交互能点通。
 */
function matchQueryString(allValues: string[], queryString: string): boolean {
  const keywords = (queryString.match(/"([^"]+)"|'([^']+)'|([^\s():><=!]+)/g) || [])
    .map(item => item.replace(/^["']|["']$/g, '').trim())
    .filter(item => item && !QUERY_STRING_KEYWORDS.includes(item));
  if (!keywords.length) return true;
  const joined = allValues.join(' ').toLocaleLowerCase();
  return keywords.some(keyword => joined.includes(keyword.toLocaleLowerCase()));
}

function matchWhereItem<T>(row: T, item: IWhereItem, getFieldValue: TFieldValueGetter<T>, allValues: string[]): boolean {
  const method = String(item.method || item.operator || 'equal');
  const rowValues = item.key === '*' ? allValues : toComparableList(getFieldValue(row, item.key));

  if (EXISTS_METHODS.includes(method)) {
    const exists = rowValues.length > 0;
    return method === 'exists' ? exists : !exists;
  }

  const values = (item.value || []).map(value => String(value));
  if (!values.length) return true;

  const hit = values.some(value => matchOne(rowValues, value, method));
  return NOT_METHODS.includes(method) ? !hit : hit;
}

function readPanelFilterMockFlag(): boolean {
  if (cachedOn !== null) return cachedOn;
  const fromSearch = new URLSearchParams(window.location.search).get('panelFilterMock');
  const hash = window.location.hash || '';
  const queryIndex = hash.indexOf('?');
  const fromHash = queryIndex >= 0 ? new URLSearchParams(hash.slice(queryIndex)).get('panelFilterMock') : '';
  cachedOn = ['1', 'true'].includes((fromHash || fromSearch || '').trim());
  return cachedOn;
}

function toComparableList(raw: unknown): string[] {
  if (raw === null || raw === undefined || raw === '') return [];
  if (Array.isArray(raw)) return raw.flatMap(item => toComparableList(item));
  if (typeof raw === 'object') {
    const item = raw as Record<string, unknown>;
    // 事件接口的单元格结构为 { value, alias }
    if ('value' in item || 'alias' in item) {
      return [...toComparableList(item.value), ...toComparableList(item.alias)];
    }
    return [];
  }
  return [String(raw)];
}
