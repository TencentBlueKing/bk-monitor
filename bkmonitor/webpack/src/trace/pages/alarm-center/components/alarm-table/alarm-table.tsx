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
import { defineComponent, computed, type PropType, useTemplateRef, onMounted } from 'vue';

import { PrimaryTable, type TableSort, type SortInfo } from '@blueking/tdesign-ui';

import { useTableCell } from '../../../trace-explore/components/trace-explore-table/hooks/use-table-cell';
import { useTableEllipsis } from '../../../trace-explore/components/trace-explore-table/hooks/use-table-popover';

import type { TableCellRender } from '../../../trace-explore/components/trace-explore-table/typing';
import type { TableColumnItem } from '../../typings';
import type { PageInfo } from '../../typings/table';

import './alarm-table.scss';

export default defineComponent({
  name: 'AlarmTable',
  props: {
    /** 表格行数据唯一值 key 名 */
    rowKey: {
      type: String,
      default: 'id',
    },
    /** 表格渲染数据 */
    data: {
      type: Array as PropType<Record<string, any>[]>,
      default: () => [],
    },
    /** 表格列配置 */
    columns: {
      type: Array as PropType<TableColumnItem[]>,
      default: () => [],
    },
    /** 表格分页当前页码 */
    currentPage: {
      type: Number,
      default: 1,
    },
    /** 表格排序信息 */
    pageSize: {
      type: Number,
      default: 20,
    },
    /** 表格数据总条数 */
    total: {
      type: Number,
      default: 0,
    },
    /** 表格单元格自定义渲染集合 key => customerRenderType,  value => TableCellRender */
    customCellRenderMap: {
      type: Object as PropType<Record<string, TableCellRender>>,
    },
  },
  emits: {
    onCurrentPageChange: (currentPage: number) => typeof currentPage === 'number',
    onPageSizeChange: (pageSize: number) => typeof pageSize === 'number',
    onSortChange: (sortEvent: SortInfo) => typeof sortEvent === 'object',
  },
  setup(props, { emit }) {
    const tableRef = useTemplateRef<InstanceType<typeof PrimaryTable>>('tableRef');

    /** 表格单元格渲染逻辑 */
    const { tableCellRender } = useTableCell({
      rowKeyField: props.rowKey,
      customCellRenderMap: props.customCellRenderMap,
    });

    /** 表格功能单元格内容溢出弹出 popover 功能 */
    const { initListeners: initEllipsisListeners } = useTableEllipsis(tableRef);

    /** 处理后的表格列配置 */
    const tableColumns = computed(() =>
      props.columns.map(column => ({ ...column, cell: (_, { row }) => tableCellRender(column, row) }))
    );

    onMounted(() => {
      setTimeout(() => {
        initEllipsisListeners();
      }, 300);
    });

    /**
     * @description 表格排序变化后回调
     * @param {TableSort} sort
     */
    function handleSortChange(sortEvent: TableSort) {
      emit('onSortChange', sortEvent as SortInfo);
    }

    /**
     * @description 表格分页变化后回调
     * @param {PageInfo} pageEvent
     */
    function handleCurrentPageChange(pageEvent: PageInfo) {
      if (pageEvent.pageSize !== props.pageSize) {
        emit('onPageSizeChange', pageEvent.pageSize);
      }
      emit('onCurrentPageChange', pageEvent.current);
    }

    return {
      tableColumns,
      tableCellRender,
      handleSortChange,
      handleCurrentPageChange,
    };
  },
  render() {
    return (
      <div class='alarm-table-wrapper'>
        <PrimaryTable
          ref='tableRef'
          class='alarm-table'
          columns={this.tableColumns}
          data={this.data}
          disableDataPage={true}
          pagination={{ current: this.currentPage, pageSize: this.pageSize, total: this.total }}
          rowKey={this.rowKey}
          onPageChange={this.handleCurrentPageChange}
          onSortChange={this.handleSortChange}
          {...this.$attrs}
          {...this.$emit}
        />
      </div>
    );
  },
});
