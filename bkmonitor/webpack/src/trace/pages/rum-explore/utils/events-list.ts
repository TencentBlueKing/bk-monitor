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
 * documentation files (the "Software"), to deal in the Software without restriction, including without limitation the
 * rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
 * permit persons to whom the Software is furnished to do so, subject to the following conditions:
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

import { ARRAY_ITEM_EMPTY_PLACEHOLDER, formatArrayItem } from './array-field-formatter';

import type { IEventsListColumn, IRumSpanRecord } from '../typings';

/**
 * @description 把一条 span 的 events 字段按数组下标展开成表格行。
 *              各 events.* 字段的值按数组处理（非数组视为单项），行数取最长数组的长度，该下标缺值补空占位符。
 * @param {IRumSpanRecord | null} row 当前行数据
 * @param {IEventsListColumn[]} columns 参与展示的列
 * @returns {Record<string, unknown>[]} 表格行，以字段名为键，另含 index 下标
 */
export function buildEventsListRows(
  row: IRumSpanRecord | null,
  columns: IEventsListColumn[]
): Record<string, unknown>[] {
  if (!row || !columns.length) return [];
  const lists = columns.map(column => {
    const value = row[column.name];
    if (value === null || value === undefined) return [];
    /** 非数组值按单项处理，与主表单元格口径一致 */
    return Array.isArray(value) ? value : [value];
  });
  const size = lists.reduce((max, list) => Math.max(max, list.length), 0);
  if (!size) return [];
  return Array.from({ length: size }, (_, index) => {
    const item: Record<string, unknown> = { index };
    columns.forEach((column, columnIndex) => {
      item[column.name] =
        index < lists[columnIndex].length
          ? formatArrayItem(lists[columnIndex][index], column.formatter)
          : ARRAY_ITEM_EMPTY_PLACEHOLDER;
    });
    return item;
  });
}
