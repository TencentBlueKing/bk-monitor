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
import { computed, shallowRef, unref } from 'vue';
import type { MaybeRef } from 'vue';

import { ORIGIN_NESTED_KEYS } from '../constants';

import type { IRumOriginBlockVM, IRumOriginRowVM } from '../typings';

/** 折叠时单行摘要里展示的键值对数量上限，超出由 CSS 省略 */
const SUMMARY_ITEM_LIMIT = 8;

/**
 * @description 原始数据面板：把 origin_data 拆成 Span / Attributes / Resource / Links / Events 五个折叠块
 *
 * Links 按 trace_id 分组，Events 按事件名分组（SENT / RECEIVED 等），Events 支持在块内按键或值搜索过滤。
 */
export function useOriginData(originData: MaybeRef<Record<string, any> | undefined>) {
  /** Events 块内的搜索关键字 */
  const eventKeyword = shallowRef('');

  const blocks = computed<IRumOriginBlockVM[]>(() => {
    const data = unref(originData);
    if (!data) return [];

    /** Span 块：顶层标量字段，嵌套字段各自有独立块 */
    const spanRows = Object.entries(data)
      .filter(([key]) => !ORIGIN_NESTED_KEYS.has(key))
      .map(([key, value]) => toRow(key, value));
    const attributeRows = toRows(data.attributes);
    const resourceRows = toRows(data.resource);

    /** 块内搜索关键字，只作用于 Events（Links 未开启 searchable） */
    const keyword = eventKeyword.value.trim().toLowerCase();
    /** Links 块：按链路分组，组名为 trace_id，组内为顶层字段 + attributes */
    const linkGroups = ((data.links || []) as Array<Record<string, any>>).map((link, index) => ({
      name: String(link.trace_id || `link_${index + 1}`),
      rows: [
        ...Object.entries(link)
          .filter(([key]) => key !== 'attributes')
          .map(([key, value]) => toRow(key, value)),
        ...toRows(link.attributes),
      ],
    }));
    /** Events 块：按事件名分组，组内为 timestamp + attributes；有关键字时只保留键或值命中的行 */
    const eventGroups = ((data.events || []) as Array<Record<string, any>>).map((event, index) => {
      const rows = [
        ...(event.timestamp === undefined ? [] : [toRow('timestamp', event.timestamp)]),
        ...toRows(event.attributes),
      ];
      return {
        name: String(event.name ?? `event_${index}`),
        rows: keyword
          ? rows.filter(row => row.key.toLowerCase().includes(keyword) || row.value.toLowerCase().includes(keyword))
          : rows,
      };
    });

    const result: IRumOriginBlockVM[] = [];
    if (spanRows.length) result.push({ key: 'span', title: 'Span', rows: spanRows, summary: toSummary(spanRows) });
    if (attributeRows.length) {
      result.push({ key: 'attributes', title: 'Attributes', rows: attributeRows, summary: toSummary(attributeRows) });
    }
    if (resourceRows.length) {
      result.push({ key: 'resource', title: 'Resource', rows: resourceRows, summary: toSummary(resourceRows) });
    }
    /** Links 块：不含搜索框，与 Events 共用分组渲染，靠 searchable 区分 */
    if (linkGroups.length) {
      result.push({
        key: 'links',
        title: `Links (${linkGroups.length})`,
        groups: linkGroups,
        summary: toSummary(linkGroups.flatMap(group => group.rows)),
      });
    }
    if (eventGroups.length) {
      result.push({
        key: 'events',
        title: `Events (${eventGroups.length})`,
        groups: eventGroups,
        searchable: true,
        summary: toSummary(eventGroups.flatMap(group => group.rows)),
      });
    }

    return result;
  });

  return { blocks, eventKeyword };
}

/** 按值的运行时类型决定前置的数据类型图标 */
function resolveValueType(value: unknown): IRumOriginRowVM['valueType'] {
  if (typeof value === 'number') return 'number';
  if (typeof value === 'boolean') return 'boolean';
  if (value && typeof value === 'object') return 'object';
  return 'string';
}

function toRow(key: string, value: unknown): IRumOriginRowVM {
  const valueType = resolveValueType(value);
  return {
    key,
    valueType,
    value: valueType === 'object' ? JSON.stringify(value, null, 2) : String(value ?? ''),
  };
}

/** 把对象铺平成键值行，嵌套对象整体序列化（原始数据面板只做一层展开） */
function toRows(source: Record<string, unknown> | undefined): IRumOriginRowVM[] {
  if (!source) return [];
  return Object.entries(source).map(([key, value]) => toRow(key, value));
}

function toSummary(rows: IRumOriginRowVM[]): string {
  return rows
    .slice(0, SUMMARY_ITEM_LIMIT)
    .map(row => `${row.key} = ${row.value}`)
    .join(' | ');
}
