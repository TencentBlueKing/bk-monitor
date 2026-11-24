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
import { computed } from 'vue';

import { isRumFieldSortable, RUM_RECORD_ID_FIELD_MAP } from '../../../constants';
import { mapSortKeys, resolveColumnLayout } from '../column-builder/column-layout';
import { buildRumColumnRenderer } from '../column-builder/column-renderer';

import type { BaseTableColumn } from '../../../../trace-explore/components/trace-explore-table/typing';
import type { IRumField, IRumSpanRecord, RumModeType } from '../../../typings';
import type { FieldAnalysisSelection } from '../components/column-header/column-header';
import type { FieldActions } from '../components/field-value/field-value';

/** 列渲染器通过这些回调将用户操作交给表格。 */
export interface RumColumnActions extends FieldActions {
  /** 判断当前行和数组列是否对应已打开的抽屉。 */
  isActive: (rowId: string, fieldName: string) => boolean;
  /** 打开数组字段所属记录的抽屉。 */
  onEventsCellClick: (row: IRumSpanRecord, fieldName: string) => void;
  /** 打开表头分析并传递已解析的候选字段。 */
  onFieldAnalysis: (trigger: Element, selection: FieldAnalysisSelection) => void;
}

/**
 * 组装展示列及排序映射，保留表格列键和请求字段的各自语义。
 * @param props 表格基础列和当前检索状态
 * @param getFields 读取完整字段索引
 * @param actions 表格业务回调
 */
export const useRumColumns = (
  props: {
    /** 由视图配置和用户偏好合成的基础列。 */
    baseColumns: BaseTableColumn[];
    /** 决定行标识和字段操作的当前视角。 */
    mode: RumModeType;
    /** 请求使用的字段排序，降序字段带减号前缀。 */
    sort?: string | string[];
    /** 全局时区切换时重新生成渲染回调。 */
    timezone: string;
  },
  getFields: () => ReadonlyMap<string, IRumField>,
  actions: RumColumnActions
) => {
  const rowKey = computed(() => RUM_RECORD_ID_FIELD_MAP[props.mode]);

  const resolved = computed(() => {
    // 时间列格式化读取全局时区，切换时要重建表格列以触发单元格更新。
    const { timezone, mode } = props;
    const fields = getFields();
    const sortFields = new Map<string, string>();
    const columns = props.baseColumns.map(column => {
      const field = fields.get(column.colKey);
      const layout = resolveColumnLayout(field, fields);
      const sortField = layout.sortField;
      const sortable = layout.sections ? !!sortField && isRumFieldSortable(sortField) : column.sorter;
      if (sortable && sortField) sortFields.set(column.colKey, sortField.name);
      return { ...column, ...buildRumColumnRenderer(column, field, layout, mode, actions), sorter: sortable };
    });

    const sortColumns = new Map<string, string>();
    for (const [column, fieldName] of sortFields) {
      if (column === fieldName || !sortColumns.has(fieldName)) sortColumns.set(fieldName, column);
    }
    return { columns, sortFields, sortColumns, timezone };
  });

  return {
    /** 当前视角使用的行标识字段。 */
    rowKey,
    /** 供 CommonTable 渲染的列配置。 */
    columns: computed(() => resolved.value.columns),
    /** 将请求字段换成表头列键，用于同步排序状态。 */
    tableSort: computed(() => mapSortKeys(props.sort, resolved.value.sortColumns)),
    /** 将表头列键还原为列表请求使用的排序字段。 */
    toQuerySort: (sort: string | string[]) => mapSortKeys(sort, resolved.value.sortFields),
  };
};
