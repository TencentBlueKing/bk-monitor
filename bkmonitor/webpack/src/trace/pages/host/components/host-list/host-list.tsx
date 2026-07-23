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

import { type PropType, computed, defineComponent, toRef } from 'vue';

import { Loading } from 'bkui-vue';
import { storeToRefs } from 'pinia';
import { useHostStore } from 'trace/store/modules/host';

import { useHostList } from '../../composables/use-host-list';
import HostListFilter from './host-list-filter';
import HostListTable from './host-list-table';
import HostListToolbar from './host-list-toolbar';
import HostStatCards from './host-stat-cards';

import type { EHostQuickCategory } from '../../types/host-list';
import type { IHostTopoTreeNode } from '../../types/topo';

import './host-list.scss';

export default defineComponent({
  name: 'HostList',
  props: {
    /** 当前选中的拓扑节点（联动过滤主机列表） */
    selectedNode: {
      type: Object as PropType<IHostTopoTreeNode | null>,
      default: null,
    },
  },
  setup(props) {
    const { where, filterExpanded, activeCategory, keyword } = storeToRefs(useHostStore());
    const ctx = useHostList({
      selectedNode: toRef(props, 'selectedNode'),
      where,
      filterExpanded,
      activeCategory,
      keyword,
    });

    const hasSelection = computed(() => ctx.selectedRowKeys.value.length > 0);

    return () => (
      <Loading
        class='host-list'
        loading={ctx.loading.value}
      >
        <HostStatCards
          activeKey={ctx.activeCategory.value}
          stats={ctx.categoryStats.value}
          onCardClick={(key: EHostQuickCategory) => ctx.handleCategoryClick(key)}
        />
        <div class='host-list__filter-bar'>
          <HostListToolbar
            filterExpanded={ctx.filterExpanded.value}
            hasSelection={hasSelection.value}
            keyword={ctx.keyword.value}
            onCopyIp={ctx.handleCopyIp}
            onKeywordChange={ctx.handleKeywordChange}
            onSearch={ctx.handleSearch}
            onToggleFilter={ctx.toggleFilterExpand}
          />
          {ctx.filterExpanded.value && (
            <HostListFilter
              fields={ctx.filterFields}
              filterMode={ctx.filterMode.value}
              filterOptionsMap={ctx.filterOptionsMap.value}
              getValueFn={ctx.getValueFn}
              queryString={ctx.queryString.value}
              where={ctx.where.value}
              onModeChange={ctx.handleFilterModeChange}
              onQueryStringChange={ctx.handleQueryStringChange}
              onSearch={ctx.handleSearch}
              onWhereChange={ctx.handleWhereChange}
            />
          )}
        </div>
        <HostListTable
          aggMethodList={ctx.aggMethodList}
          aggMethodMap={ctx.aggMethodMap.value}
          data={ctx.pagedRows.value}
          metricLoading={ctx.metricLoading.value}
          page={ctx.page.value}
          pageSize={ctx.pageSize.value}
          selectedRowKeys={ctx.selectedRowKeys.value}
          sort={ctx.sortInfo.value}
          total={ctx.total.value}
          visibleColumns={ctx.visibleColumns.value}
          onAggMethodChange={ctx.handleAggMethodChange}
          onColumnsChange={ctx.handleColumnsChange}
          onPageChange={ctx.handlePageChange}
          onPageSizeChange={ctx.handlePageSizeChange}
          onSelectChange={ctx.handleSelectChange}
          onSortChange={ctx.handleSortChange}
        />
      </Loading>
    );
  },
});
