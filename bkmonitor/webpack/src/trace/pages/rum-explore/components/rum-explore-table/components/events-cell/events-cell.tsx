import { type PropType, computed, defineComponent } from 'vue';

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
import { ARRAY_ITEM_EMPTY_PLACEHOLDER, formatArrayItem, resolveArrayItemFormatter } from '../../../../utils';
import CollapseArrayCell from '../collapse-array-cell/collapse-array-cell';

import type {
  BaseTableColumn,
  TableCellRenderContext,
} from '../../../../../trace-explore/components/trace-explore-table/typing';
import type { IRumField, IRumSpanRecord } from '../../../../typings';

import './events-cell.scss';

export default defineComponent({
  name: 'RumEventsCell',
  props: {
    /** 当前数组抽屉是否对应这个单元格。 */
    active: { type: Boolean, default: false },
    /** 当前列键和折叠展示所需的表格列配置。 */
    column: { type: Object as PropType<BaseTableColumn>, required: true },
    /** 共享表格的行标识和单元格渲染上下文。 */
    ctx: { type: Object as PropType<TableCellRenderContext>, required: true },
    /** 用于格式化数组成员的字段元信息。 */
    field: { type: Object as PropType<IRumField>, default: undefined },
    /** 包含原始数组值的检索记录。 */
    row: { type: Object as PropType<IRumSpanRecord>, required: true },
  },
  emits: {
    /** 打开当前行对应的数组详情抽屉。 */
    open: () => true,
  },
  setup(props, { emit }) {
    const values = computed(() => {
      const formatter = resolveArrayItemFormatter(props.field);
      const value = props.row[props.column.colKey];
      const list = Array.isArray(value) ? value : [value];
      return list.length ? list.map(item => formatArrayItem(item, formatter)) : [ARRAY_ITEM_EMPTY_PLACEHOLDER];
    });

    /** 通知表格打开数组抽屉。 */
    const handleOpen = () => emit('open');

    return { values, handleOpen };
  },
  render() {
    return (
      <div
        class={['rum-array-col-trigger', { 'is-active': this.active }]}
        onClick={this.handleOpen}
      >
        <CollapseArrayCell
          class='rum-collapse-array-col'
          column={this.column}
          minVisibleCount={1}
          renderCtx={this.ctx}
          rowId={this.ctx.getRowId?.(this.row)}
          values={this.values}
        />
      </div>
    );
  },
});
