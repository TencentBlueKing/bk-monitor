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
import { type MaybeRef, onBeforeUnmount } from 'vue';

import { get } from '@vueuse/core';

/** table 行的唯一 Key 类型 */
type TableRowId = string;

/**
 * @description Explore 数据缓存 Hook
 * 用于缓存 Explore 表格行数据，提供快速访问和复杂值获取功能
 * @param rowKeyField 行数据中唯一标识的字段名，trace检索中主要是 traceId 或 spanId
 * @remarks
 * 1. 该 Hook 主要用于 Explore 表格数据的缓存和快速访问。
 * 2. `rowKeyField` 必须是行数据中唯一标识的字段名，通常是 traceId 或 spanId。
 * 3. `getCellComplexValue` 方法支持获取数组中的特定下标值或对象的特定字段值，提供灵活的数据访问方式。
 * 主要是配合事件委任时能够通过主要的key定位更好的获取复杂行数据。
 */
export function useExploreDataCache(rowKeyField: MaybeRef<string>) {
  /** 缓存Map，key为唯一rowKey，value为行数据 */
  let rowDataCache = new Map<TableRowId, Record<string, any>>();

  /**
   * 批量缓存行数据
   * @param rows 接口返回的数组数据
   */
  function cacheRows(rows: Record<string, any>[]) {
    const keyField = get(rowKeyField);
    for (const row of rows) {
      const rowKey = row?.[keyField];
      if (rowKey !== undefined && rowKey !== null) {
        rowDataCache.set(rowKey, row);
      }
    }
  }

  /**
   * 获取某一行数据
   * @param rowKey 行唯一key
   */
  function getRow(rowKey: TableRowId) {
    return rowDataCache.get(rowKey);
  }

  /**
   * 获取某一行的某一列的复杂值
   * @param rowKey 行唯一key
   * @param colKey 列字段名
   * @param options 可选，包含 index/field 等
   */
  function getCellComplexValue(rowKey: TableRowId, colKey: string, options?: { field?: string; index?: number }) {
    const row = getRow(rowKey);
    if (!row) return undefined;
    let value = row[colKey];

    // 如果是数组且有 index，取对应下标
    if (Array.isArray(value) && typeof options?.index === 'number') {
      value = value[options.index];
    }

    // 如果有 field，取对象的 field 属性
    if (value && typeof options?.field === 'string' && typeof value === 'object') {
      value = value[options.field];
    }

    return value;
  }

  /**
   * 清空缓存
   */
  function clearCache() {
    rowDataCache.clear();
  }

  onBeforeUnmount(() => {
    clearCache();
    rowDataCache = null;
  });

  return {
    rowDataCache,
    cacheRows,
    getRow,
    getCellComplexValue,
    clearCache,
  };
}
