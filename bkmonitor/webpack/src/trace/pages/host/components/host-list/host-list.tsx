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

import { Alert, Button } from 'bkui-vue';
import { storeToRefs } from 'pinia';
import { useHostStore } from 'trace/store/modules/host';
import { useI18n } from 'vue-i18n';

import { useHostList } from '../../composables/use-host-list';
import HostListFilter from './host-list-filter';
import HostListTable from './host-list-table';
import HostListToolbar from './host-list-toolbar';
import HostStatCards from './host-stat-cards';

import type { EHostQuickCategory, IHostListRow } from '../../types/host-list';
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
    readonly: {
      type: Boolean,
      default: false,
    },
  },
  emits: {
    selectIpCell: (_row: IHostListRow) => true,
    processClick: (_row: IHostListRow, _processName: string) => true,
  },
  setup(props, { emit }) {
    const { t } = useI18n();
    const { where, filterExpanded, activeCategory, keyword } = storeToRefs(useHostStore());
    const ctx = useHostList({
      readonly: props.readonly,
      selectedNode: toRef(props, 'selectedNode'),
      where,
      filterExpanded,
      activeCategory,
      keyword,
    });

    const hasSelection = computed(() => ctx.selectedRowKeys.value.size > 0);
    const hasPausedConditions = computed(
      () =>
        !ctx.fullDataReady.value &&
        !!(
          ctx.keyword.value ||
          ctx.where.value.length ||
          ctx.queryString.value ||
          ctx.activeCategory.value ||
          ctx.sortInfo.value ||
          Object.keys(ctx.stickyValue.value).length
        )
    );

    /** 点击主机列表 IP 单元格时，向上冒泡到页面层处理拓扑树聚焦 */
    const handleSelectIpCell = row => {
      emit('selectIpCell', row);
    };

    return () => (
      <div class='host-list'>
        <div class='host-list-content'>
          <HostStatCards
            activeKey={ctx.activeCategory.value}
            fullDataReady={ctx.fullDataReady.value}
            states={ctx.categoryStates.value}
            stats={ctx.categoryStats.value}
            onCardClick={(key: EHostQuickCategory) => ctx.handleCategoryClick(key)}
            onRetry={ctx.retryCategory}
          />
          {!ctx.fullDataReady.value && (
            <Alert
              class='host-list__full-status'
              theme={ctx.fullLoadError.value ? 'warning' : 'info'}
            >
              {{
                title: () => (
                  <div>
                    <span>
                      {ctx.fullLoadError.value
                        ? t('全量数据加载失败，可继续按页浏览')
                        : t('全量数据加载中，可继续翻页；排序和筛选暂不可用')}
                    </span>
                    {ctx.fullLoadError.value && (
                      <Button
                        class='host-list__full-retry'
                        disabled={ctx.fullLoading.value}
                        text
                        onClick={ctx.retryFullData}
                      >
                        {t('重新加载')}
                      </Button>
                    )}
                    {hasPausedConditions.value && (
                      <div>{t('已保存的筛选、排序和置顶条件暂未应用，将在全量数据加载完成后生效')}</div>
                    )}
                  </div>
                ),
              }}
            </Alert>
          )}
          <div class='host-list__filter-bar'>
            <HostListToolbar
              disabled={!ctx.fullDataReady.value}
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
                disabled={!ctx.fullDataReady.value}
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
            emptyType={
              ctx.fullDataReady.value && ctx.rawRowCount.value > 0 && ctx.total.value === 0 ? 'search-empty' : 'empty'
            }
            columnWidths={ctx.fieldsWidthConfig.value}
            data={ctx.pagedRows.value}
            fullDataReady={ctx.fullDataReady.value}
            loadError={ctx.loadError.value}
            loading={ctx.loading.value}
            markValue={ctx.fullDataReady.value ? ctx.stickyValue.value : {}}
            metricLoadError={ctx.metricLoadError.value}
            metricLoading={ctx.metricLoading.value}
            page={ctx.page.value}
            pageSize={ctx.pageSize.value}
            readonly={props.readonly}
            selectedRowKeys={ctx.selectedRowKeys.value}
            selectType={ctx.selectType.value}
            sort={ctx.fullDataReady.value ? ctx.sortInfo.value : ''}
            total={ctx.total.value}
            visibleColumns={ctx.visibleColumns.value}
            onClearFilter={ctx.handleClearFilter}
            onColumnResize={(widths: Record<string, number>) => (ctx.fieldsWidthConfig.value = widths)}
            onColumnsChange={ctx.handleColumnsChange}
            onHeaderSelect={ctx.handleHeaderSelect}
            onIpMark={ctx.handleIpMark}
            onPageChange={ctx.handlePageChange}
            onPageSizeChange={ctx.handlePageSizeChange}
            onProcessClick={(...args) => emit('processClick', ...args)}
            onRetryMetric={ctx.loadMetricData}
            onRetryPage={ctx.loadPageData}
            onRowCheck={ctx.handleRowCheck}
            onSelectIpCell={handleSelectIpCell}
            onSortChange={ctx.handleSortChange}
          />
        </div>
      </div>
    );
  },
});
