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

import { type PropType, defineComponent, onBeforeUnmount, onMounted, useTemplateRef } from 'vue';

import CommonTable from '../../components/alarm-table/components/common-table/common-table';
import { usePopover } from '../../components/alarm-table/hooks/use-popover';
import { CONTENT_SCROLL_ELEMENT_CLASS_NAME } from '../../typings';
import { useIssuesColumns } from './issues-columns';
import { useIssuesHandlers } from './use-issues-handlers';

import type { TablePagination } from '../../typings';
import type { IssueItem, IssuePriorityType } from '../typing';
import type { SelectOptions } from 'tdesign-vue-next';

import './issues-table.scss';

export default defineComponent({
  name: 'IssuesTable',
  props: {
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
  },
  emits: {
    currentPageChange: (currentPage: number) => typeof currentPage === 'number',
    pageSizeChange: (pageSize: number) => typeof pageSize === 'number',
    sortChange: (sort: string | string[]) => typeof sort === 'string' || Array.isArray(sort),
    selectionChange: (selectedRowKeys: string[], _options?: SelectOptions<unknown>) => Array.isArray(selectedRowKeys),
    showDetail: (id: string) => typeof id === 'string',
    assign: (id: string, assignee: string[]) => typeof id === 'string' && Array.isArray(assignee),
    markResolved: (id: string) => typeof id === 'string',
    priorityChange: (id: string, priority: IssuePriorityType) => typeof id === 'string' && !!priority,
  },
  setup(_props, { emit }) {
    const tableRef = useTemplateRef<InstanceType<typeof CommonTable>>('tableRef');
    /** click 场景使用的 popover 工具 */
    const clickPopoverTools = usePopover({
      showDelay: 100,
      tippyOptions: {
        trigger: 'click',
        placement: 'bottom',
        theme: 'light alarm-center-popover max-width-50vw text-wrap padding-0',
      },
    });
    /** 滚动容器元素 */
    let scrollContainer: HTMLElement = null;
    /** 滚动结束后回调逻辑执行计时器 */
    let scrollPointerEventsTimer: null | ReturnType<typeof setTimeout> = null;

    const { handleShowDetail, handleAssignClick, handleMarkResolved, handlePriorityClick, renderAssignDialog } =
      useIssuesHandlers({
        clickPopoverTools,
        showDetailEmit: id => emit('showDetail', id),
        assignEmit: (id, assignee) => emit('assign', id, assignee),
        markResolvedEmit: id => emit('markResolved', id),
        priorityChangeEmit: (id, priority) => emit('priorityChange', id, priority),
      });

    /** Issues 表格列配置 */
    const { columns } = useIssuesColumns({
      handleShowDetail,
      handleAssignClick,
      handleMarkResolved,
      handlePriorityClick,
    });

    // 配置表格是否能够触发事件 target
    const updateTablePointerEvents = (val: 'auto' | 'none') => {
      const tableDom = tableRef?.value?.$el;
      if (!tableDom) return;
      tableDom.style.pointerEvents = val;
    };

    // 滚动触发事件
    const handleScroll = () => {
      updateTablePointerEvents('none');
      clickPopoverTools.hidePopover();
      scrollPointerEventsTimer && clearTimeout(scrollPointerEventsTimer);
      scrollPointerEventsTimer = setTimeout(() => {
        updateTablePointerEvents('auto');
      }, 600);
    };

    // 添加滚动监听
    const addScrollListener = () => {
      removeScrollListener();
      scrollContainer = document.querySelector(`.${CONTENT_SCROLL_ELEMENT_CLASS_NAME}`);
      if (!scrollContainer) return;
      scrollContainer.addEventListener('scroll', handleScroll);
    };

    // 移除滚动监听
    const removeScrollListener = () => {
      if (!scrollContainer) return;
      scrollContainer.removeEventListener('scroll', handleScroll);
      scrollContainer = null;
    };

    /**
     * @description 处理行选择变化
     * @param keys - 选中行 keys
     * @param options - 选择选项
     */
    const handleSelectionChange = (keys?: (number | string)[], options?: SelectOptions<unknown>) => {
      emit('selectionChange', (keys ?? []) as string[], options);
    };

    onMounted(() => {
      addScrollListener();
    });

    onBeforeUnmount(() => {
      scrollPointerEventsTimer && clearTimeout(scrollPointerEventsTimer);
      removeScrollListener();
    });

    return {
      columns,
      handleSelectionChange,
      renderAssignDialog,
    };
  },
  render() {
    return (
      <div class='issues-table'>
        <CommonTable
          ref='tableRef'
          class='issues-table-main'
          headerAffixedTop={{
            container: `.${CONTENT_SCROLL_ELEMENT_CLASS_NAME}`,
          }}
          horizontalScrollAffixedBottom={{
            container: `.${CONTENT_SCROLL_ELEMENT_CLASS_NAME}`,
          }}
          autoFillSpace={!this.data?.length}
          columns={this.columns}
          data={this.data}
          loading={this.loading}
          pagination={this.pagination}
          selectedRowKeys={this.selectedRowKeys}
          sort={this.sort}
          onCurrentPageChange={page => this.$emit('currentPageChange', page)}
          onPageSizeChange={pageSize => this.$emit('pageSizeChange', pageSize)}
          onSelectChange={this.handleSelectionChange}
          onSortChange={sort => this.$emit('sortChange', sort)}
        />

        {/* 指派负责人弹窗 DOM 挂载 */}
        <div style='display: none;'>{this.renderAssignDialog()}</div>
      </div>
    );
  },
});
