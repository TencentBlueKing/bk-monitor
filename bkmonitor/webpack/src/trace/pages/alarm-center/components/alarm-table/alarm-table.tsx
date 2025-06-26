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

import { PrimaryTable, type TableSort } from '@blueking/tdesign-ui';
import { Pagination } from 'bkui-vue';

import TableSkeleton from '../../../../components/skeleton/table-skeleton';
import { useTableCell } from '../../../trace-explore/components/trace-explore-table/hooks/use-table-cell';
import { useTableEllipsis } from '../../../trace-explore/components/trace-explore-table/hooks/use-table-popover';

import type { TableCellRender } from '../../../trace-explore/components/trace-explore-table/typing';
import type { TableColumnItem } from '../../typings';
import type { TdAffixProps } from 'tdesign-vue-next';

import './alarm-table.scss';

export default defineComponent({
  name: 'AlarmTable',
  props: {
    /** 表格行数据唯一值 key 名 */
    rowKey: {
      type: String,
      default: 'id',
    },
    /** 表格列配置 */
    columns: {
      type: Array as PropType<TableColumnItem[]>,
      default: () => [],
    },
    /** 表格渲染数据 */
    data: {
      type: Array as PropType<Record<string, any>[]>,
      default: () => [],
    },
    /** 表格排序信息,字符串格式，以id为例：倒序 => -id；正序 => id；*/
    sort: {
      type: [String, Array] as PropType<string | string[]>,
    },
    /** 表格数据总条数 */
    total: {
      type: Number,
      default: 0,
    },
    /** 是否启用分页 */
    enabledPagination: {
      type: Boolean,
      default: true,
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
    /** 表格加载状态 */
    loading: {
      type: Boolean,
      default: false,
    },
    /** 表头吸顶。使用该功能，需要非常注意表格是相对于哪一个父元素进行滚动 */
    headerAffixedTop: {
      type: [Boolean, Object] as PropType<boolean | TdAffixProps>,
    },
    /** 滚动条吸底 */
    horizontalScrollAffixedBottom: {
      type: [Boolean, Object] as PropType<boolean | TdAffixProps>,
    },
    /** 表格单元格自定义渲染集合 key => customerRenderType,  value => TableCellRender */
    customCellRenderMap: {
      type: Object as PropType<Record<string, TableCellRender>>,
    },
  },
  emits: {
    currentPageChange: (currentPage: number) => typeof currentPage === 'number',
    pageSizeChange: (pageSize: number) => typeof pageSize === 'number',
    sortChange: (sort: string | string[]) => typeof sort === 'string' || Array.isArray(sort),
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
    /** 表格骨架屏展示相关配置 */
    const tableSkeletonConfig = computed(() => {
      if (!props.loading) return null;
      const config = {
        tableClass: 'alarm-table-hidden-body',
        skeletonClass: 'alarm-skeleton-show-body',
      };
      return config;
    });
    /** 是否展示分页器 */
    const showPagination = computed(() => props.enabledPagination && props.data?.length);
    /** 表格排序，将字符串形式转换成 TableSort 形式 */
    const tableSort = computed(() => {
      // 统一处理为数组形式
      const sortRules = Array.isArray(props.sort) ? props.sort : [props.sort];
      const parsedSorts = [];

      for (const rule of sortRules) {
        if (!rule) continue;

        // 解析排序规则字符串
        const isDescending = rule.startsWith('-');
        const sortField = isDescending ? rule.slice(1) : rule;

        if (sortField) {
          parsedSorts.push({
            sortBy: sortField,
            descending: isDescending,
          });
        }
      }

      return parsedSorts;
    });

    onMounted(() => {
      setTimeout(() => {
        initEllipsisListeners();
      }, 300);
    });

    /**
     * @description 表格排序变化后回调
     * @param {TableSort} sort
     *
     */
    function handleSortChange(sortEvent: TableSort) {
      if (Array.isArray(sortEvent)) {
        // 处理数组形式的排序
        const sortStrings = sortEvent
          .filter(item => item?.sortBy)
          .map(item => `${item.descending ? '-' : ''}${item.sortBy}`);
        emit('sortChange', sortStrings.length === 1 ? sortStrings[0] : sortStrings);
        return;
      }

      let sort = '';
      if (sortEvent.sortBy) {
        sort = `${sortEvent.descending ? '-' : ''}${sortEvent.sortBy}`;
      }
      emit('sortChange', sort);
    }

    /**
     * @description 表格当前页码变化时的回调
     *
     */
    function handleCurrentPageChange(page: number) {
      emit('currentPageChange', page);
    }

    /**
     * @description 表格每页条数变化时的回调
     *
     */
    function handlePageSizeChange(size: number) {
      emit('pageSizeChange', size);
    }

    return {
      tableColumns,
      tableSort,
      showPagination,
      tableSkeletonConfig,
      tableCellRender,
      handleSortChange,
      handleCurrentPageChange,
      handlePageSizeChange,
    };
  },
  render() {
    return (
      <div class='alarm-table-wrapper'>
        <PrimaryTable
          ref='tableRef'
          class={`alarm-table ${this.tableSkeletonConfig?.tableClass}`}
          activeRowType='single'
          columns={this.tableColumns}
          data={this.data}
          disableDataPage={true}
          headerAffixedTop={this.headerAffixedTop}
          horizontalScrollAffixedBottom={this.horizontalScrollAffixedBottom}
          hover={true}
          resizable={true}
          rowKey={this.rowKey}
          showSortColumnBgColor={true}
          size='small'
          sort={this.tableSort}
          tableLayout='fixed'
          onSortChange={this.handleSortChange}
        />
        <TableSkeleton class={`alarm-table-skeleton ${this.tableSkeletonConfig?.skeletonClass}`} />

        {this.showPagination ? (
          <Pagination
            align={'right'}
            count={this.total}
            layout={['total', 'limit', 'list']}
            limit={this.pageSize}
            location={'right'}
            modelValue={this.currentPage}
            onChange={this.handleCurrentPageChange}
            onLimitChange={this.handlePageSizeChange}
          />
        ) : null}
      </div>
    );
  },
});
