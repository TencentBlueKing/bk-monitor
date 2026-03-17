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

import { type PropType, computed, defineComponent, onBeforeMount, shallowRef, useTemplateRef, watch } from 'vue';

import { random } from 'monitor-common/utils';
import { echartsConnect, echartsDisconnect } from 'monitor-ui/monitor-echarts/utils';

import CommonTable from '../../components/alarm-table/components/common-table/common-table';
import { usePopover } from '../../components/alarm-table/hooks/use-popover';
import { useTableScrollOptimize } from '../../composables/use-table-scroll-optimize';
import { useIssuesColumnsRenderer } from './hooks/use-issues-columns-renderer';
import { useIssuesHandlers } from './hooks/use-issues-handlers';

import type { TableColumnItem, TablePagination } from '../../typings';
import type { IssueItem, IssuePriorityType } from '../typing';
import type { SelectOptions } from 'tdesign-vue-next';

import './issues-table.scss';

export default defineComponent({
  name: 'IssuesTable',
  props: {
    /** 表格列配置（静态列，由外部传入） */
    columns: {
      type: Array as PropType<TableColumnItem[]>,
      default: () => [],
    },
    /** 表格渲染数据 */
    data: {
      type: Array as PropType<IssueItem[]>,
      default: () => [],
    },
    /** 表格加载状态 */
    loading: {
      type: Boolean,
      default: false,
    },
    /** 表格分页配置 */
    pagination: {
      type: Object as PropType<TablePagination>,
    },
    /** 表格排序信息 */
    sort: {
      type: [String, Array] as PropType<string | string[]>,
    },
    /** 表格选中行 */
    selectedRowKeys: {
      type: Array as PropType<string[]>,
      default: () => [],
    },
    /** 滚动容器的 CSS 选择器（用于滚动优化及表头/滚动条吸附） */
    scrollContainerSelector: {
      type: String,
      required: true,
    },

    headerAffixedTop: {
      type: Object as PropType<{ container: string }>,
    },
    horizontalScrollAffixedBottom: {
      type: Object as PropType<{ container: string }>,
    },
  },
  emits: {
    currentPageChange: (currentPage: number) => typeof currentPage === 'number',
    pageSizeChange: (pageSize: number) => typeof pageSize === 'number',
    sortChange: (sort: string | string[]) => typeof sort === 'string' || Array.isArray(sort),
    selectionChange: (selectedRowKeys: string[], options?: SelectOptions<any>) =>
      Array.isArray(selectedRowKeys) && options,
    showDetail: (id: string) => typeof id === 'string',
    assignClick: (id: IssueItem['id'], data: IssueItem) => typeof id === 'string' && !!data,
    markResolved: (id: string) => typeof id === 'string',
    priorityChange: (id: string, priority: IssuePriorityType) => typeof id === 'string' && !!priority,
  },
  setup(props, { emit }) {
    const tableRef = useTemplateRef<InstanceType<typeof CommonTable>>('tableRef');
    /** 图表联动组 ID */
    const chartGroupId = shallowRef(random(8));

    /** click 场景使用的 popover 工具 */
    const clickPopoverTools = usePopover({
      showDelay: 100,
      tippyOptions: {
        trigger: 'click',
        placement: 'bottom',
        theme: 'light alarm-center-popover max-width-50vw text-wrap padding-0',
      },
    });

    const { handleShowDetail, handleAssignClick, handleMarkResolved, handlePriorityClick } = useIssuesHandlers({
      clickPopoverTools,
      showDetailEmit: id => emit('showDetail', id),
      assignClickEmit: (id, data) => emit('assignClick', id, data),
      markResolvedEmit: id => emit('markResolved', id),
      priorityChangeEmit: (id, priority) => emit('priorityChange', id, priority),
    });

    /** Issues 列渲染器 */
    const { transformColumns } = useIssuesColumnsRenderer({
      chartGroupId,
      clickPopoverTools,
      handleShowDetail,
      handleAssignClick,
      handleMarkResolved,
      handlePriorityClick,
    });

    /** 转换后的列配置 */
    const transformedColumns = computed(() => transformColumns(props.columns));

    /** 表格滚动优化：滚动时禁用 pointerEvents 并隐藏 popover */
    useTableScrollOptimize({
      targetElement: tableRef,
      scrollContainerSelector: props.scrollContainerSelector,
      onScroll: () => {
        clickPopoverTools.hidePopover();
      },
    });

    /**
     * @description 处理行选择变化
     * @param keys - 选中行 keys
     * @param options - 选择选项
     */
    const handleSelectionChange = (keys?: (number | string)[], options?: SelectOptions<unknown>) => {
      emit('selectionChange', (keys ?? []) as string[], options);
    };

    watch(
      () => props.data,
      () => {
        echartsDisconnect(chartGroupId.value);
        if (!props.data?.length) return;
        const newId = random(8);
        echartsConnect(newId);
        chartGroupId.value = newId;
      },
      { immediate: true }
    );

    onBeforeMount(() => {
      echartsDisconnect(chartGroupId.value);
    });
    return {
      transformedColumns,
      handleSelectionChange,
    };
  },
  render() {
    return (
      <div class='issues-table'>
        <CommonTable
          ref='tableRef'
          class='issues-table-main'
          autoFillSpace={!this.data?.length}
          columns={this.transformedColumns}
          data={this.data}
          headerAffixedTop={this.headerAffixedTop}
          horizontalScrollAffixedBottom={this.horizontalScrollAffixedBottom}
          loading={this.loading}
          pagination={this.pagination}
          selectedRowKeys={this.selectedRowKeys}
          sort={this.sort}
          onCurrentPageChange={page => this.$emit('currentPageChange', page)}
          onPageSizeChange={pageSize => this.$emit('pageSizeChange', pageSize)}
          onSelectChange={this.handleSelectionChange}
          onSortChange={sort => this.$emit('sortChange', sort)}
        />
      </div>
    );
  },
});
