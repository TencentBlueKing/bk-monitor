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

import { type PropType, computed, defineComponent, useTemplateRef } from 'vue';

import CommonTable from '../../components/alarm-table/components/common-table/common-table';
import { usePopover } from '../../components/alarm-table/hooks/use-popover';
import { useEchartsGroupConnect } from '../../composables/use-echarts-group';
import { useTableScrollOptimize } from '../../composables/use-table-scroll-optimize';
import { useIssuesColumnsRenderer } from './hooks/use-issues-columns-renderer';
import { useIssuesHandlers } from './hooks/use-issues-handlers';
import ExploreTableEmpty from '@/pages/trace-explore/components/trace-explore-table/components/explore-table-empty';

import type { TableColumnItem, TablePagination } from '../../typings';
import type { ImpactScopeEvent, IssueItem, IssuePriorityType, IssuesBatchActionType } from '../typing';
import type { SelectOptions, SlotReturnValue } from 'tdesign-vue-next';

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
    /** 表头吸顶 */
    headerAffixedTop: {
      type: Object as PropType<{ container: string }>,
    },
    /** 滚动条吸底 */
    horizontalScrollAffixedBottom: {
      type: Object as PropType<{ container: string }>,
    },
    /** 空状态下是否显示"清空筛选项"操作 */
    showEmptyOperation: {
      type: Boolean,
      default: false,
    },
  },
  emits: {
    /** 页码变化 */
    currentPageChange: (currentPage: number) => typeof currentPage === 'number',
    /** 页大小变化 */
    pageSizeChange: (pageSize: number) => typeof pageSize === 'number',
    /** 排序变化 */
    sortChange: (sort: string | string[]) => typeof sort === 'string' || Array.isArray(sort),
    /** 选择变化 */
    selectionChange: (selectedRowKeys: string[], options: SelectOptions<any>) =>
      Array.isArray(selectedRowKeys) && !!options,
    /** 显示详情 */
    showDetail: (item: IssueItem) => !!item,
    /** 分配负责人点击 */
    assignClick: (id: IssueItem['id'], data: IssueItem) => typeof id === 'string' && !!data,
    /** 状态变更操作（标记已解决/重新打开/归档/恢复归档） */
    action: (type: IssuesBatchActionType, id: string) => typeof type === 'string' && typeof id === 'string',
    /** 优先级变化 */
    priorityChange: (id: string, priority: IssuePriorityType) => typeof id === 'string' && !!priority,
    /** 影响范围点击 */
    impactScopeClick: (event: ImpactScopeEvent) => !!event,
    /** 清除检索过滤 */
    clearFilter: () => true,
  },
  setup(props, { emit }) {
    const tableRef = useTemplateRef<InstanceType<typeof CommonTable>>('tableRef');

    /** 图表联动组管理 */
    const { chartGroupId } = useEchartsGroupConnect(() => props.data);
    /** hover 场景使用的popover工具函数 */
    const hoverPopoverTools = usePopover();
    /** click 场景使用的 popover 工具 */
    const clickPopoverTools = usePopover({
      showDelay: 100,
      tippyOptions: {
        trigger: 'click',
        placement: 'bottom',
        theme: 'light alarm-center-popover max-width-50vw text-wrap padding-0',
      },
    });

    const { handleShowDetail, handleAssignClick, handleAction, handlePriorityClick, handleImpactScopeClick } =
      useIssuesHandlers({
        clickPopoverTools,
        showDetailEmit: item => emit('showDetail', item),
        assignClickEmit: (id, data) => emit('assignClick', id, data),
        actionEmit: (type, id) => emit('action', type, id),
        priorityChangeEmit: (id, priority) => emit('priorityChange', id, priority),
        impactScopeClickEmit: event => emit('impactScopeClick', event),
      });

    /** Issues 列渲染器 */
    const { transformColumns } = useIssuesColumnsRenderer({
      chartGroupId,
      clickPopoverTools,
      hoverPopoverTools,
      handleShowDetail,
      handleAssignClick,
      handleAction,
      handlePriorityClick,
      handleImpactScopeClick,
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

    return {
      transformedColumns,
    };
  },
  render() {
    return (
      <div class='issues-table'>
        <CommonTable
          ref='tableRef'
          class='issues-table-main'
          empty={() =>
            (
              <ExploreTableEmpty
                showOperation={this.showEmptyOperation}
                onClearFilter={() => this.$emit('clearFilter')}
              />
            ) as unknown as SlotReturnValue
          }
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
          onSelectChange={(keys, options) => this.$emit('selectionChange', (keys ?? []) as string[], options)}
          onSortChange={sort => this.$emit('sortChange', sort)}
        />
      </div>
    );
  },
});
