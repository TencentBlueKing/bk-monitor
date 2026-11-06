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

import type { IEventsListColumn, IRumSpanRecord } from '../typings';

/**
 * @description 把一条 span 的 events 字段按数组下标展开成表格行。
 *              各 events.* 字段的值按数组处理（非数组视为单项），行数取最长数组的长度。
 *              行内保存原始值（不格式化）：单元格展示文案由列的 getRenderValue 格式化，
 *              检索条件菜单据此取到可直接检索的原始值。空洞项 / 缺值统一为空串，对象项序列化为 JSON 文本。
 * @param {IRumSpanRecord | null} row 当前行数据
 * @param {IEventsListColumn[]} columns 参与展示的列
 * @returns {Record<string, unknown>[]} 表格行，以字段名为键，另含 index 下标与字符串行 ID rowId（span_id + 下标，跨 span 唯一；
 *          表格取行 ID 时 `|| ''` 会把第 0 行的数字下标 0 当作空值丢弃，故不直接用 index）
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
    const item: Record<string, unknown> = { index, rowId: `${row.span_id}_${index}` };
    columns.forEach((column, columnIndex) => {
      const value = lists[columnIndex][index];
      if (value === null || value === undefined) {
        item[column.name] = '';
      } else {
        item[column.name] = typeof value === 'object' ? JSON.stringify(value) : value;
      }
    });
    return item;
  });
}
