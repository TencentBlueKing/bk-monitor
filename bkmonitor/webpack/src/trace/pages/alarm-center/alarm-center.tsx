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
import { defineComponent, shallowRef } from 'vue';

import { useAlarmCenterStore } from '@/store/modules/alarm-center';

import TraceExploreLayout from '../trace-explore/components/trace-explore-layout';
import AlarmAnalysis from './components/alarm-analysis/alarm-analysis';
import AlarmCenterHeader from './components/alarm-center-header';
import AlarmRetrievalFilter from './components/alarm-retrieval-filter/alarm-retrieval-filter';
import AlarmTable from './components/alarm-table/alarm-table';
import AlarmTrendChart from './components/alarm-trend-chart/alarm-trend-chart';
import QuickFiltering from './components/quick-filtering';
import { useAlarmTable } from './composables/use-alarm-table';
import { useQuickFilter } from './composables/use-quick-filter';
import { useAlarmTableColumns } from './composables/use-table-columns';
import { CONTENT_SCROLL_ELEMENT_CLASS_NAME, type CommonCondition } from './typings';

import './alarm-center.scss';
export default defineComponent({
  name: 'AlarmCenter',
  setup() {
    const alarmStore = useAlarmCenterStore();
    const { quickFilterList, quickFilterLoading } = useQuickFilter();
    const { data, loading, total, page, pageSize, ordering } = useAlarmTable();
    const {
      tableColumns: tableSourceColumns,
      storageColumns,
      allTableFields,
      lockedTableFields,
    } = useAlarmTableColumns();
    const isCollapsed = shallowRef(false);

    const updateIsCollapsed = (v: boolean) => {
      isCollapsed.value = v;
    };

    const handleFilterValueChange = (filterValue: CommonCondition[]) => {
      alarmStore.quickFilterValue = filterValue;
    };

    return {
      quickFilterList,
      quickFilterLoading,
      isCollapsed,
      data,
      loading,
      total,
      page,
      pageSize,
      ordering,
      tableSourceColumns,
      storageColumns,
      allTableFields,
      lockedTableFields,
      alarmStore,
      handleFilterValueChange,
      updateIsCollapsed,
    };
  },
  render() {
    return (
      <div class='alarm-center'>
        <AlarmCenterHeader class='alarm-center-header' />
        <AlarmRetrievalFilter class='alarm-center-filters' />
        <div class='alarm-center-main'>
          <TraceExploreLayout
            v-slots={{
              aside: () => {
                return (
                  <div class='quick-filtering'>
                    <QuickFiltering
                      filterList={this.quickFilterList}
                      filterValue={this.alarmStore.quickFilterValue}
                      loading={this.quickFilterLoading}
                      onClose={this.updateIsCollapsed}
                      onUpdate:filterValue={this.handleFilterValueChange}
                    />
                  </div>
                );
              },
              default: () => {
                return (
                  <div class={CONTENT_SCROLL_ELEMENT_CLASS_NAME}>
                    <div class='chart-trend'>
                      <AlarmTrendChart />
                    </div>
                    <div class='alarm-analysis'>
                      <AlarmAnalysis />
                    </div>
                    <div class='alarm-center-table'>
                      <AlarmTable
                        pagination={{
                          currentPage: this.page,
                          pageSize: this.pageSize,
                          total: this.total,
                        }}
                        tableSettings={{
                          checked: this.storageColumns,
                          fields: this.allTableFields,
                          disabled: this.lockedTableFields,
                        }}
                        columns={this.tableSourceColumns}
                        data={this.data}
                        loading={this.loading}
                        sort={this.ordering}
                        // @ts-ignore
                        onCurrentPageChange={page => {
                          this.page = page;
                        }}
                        onDisplayColFieldsChange={displayColFields => {
                          this.storageColumns = displayColFields;
                        }}
                        onPageSizeChange={pageSize => {
                          this.pageSize = pageSize;
                        }}
                        onSortChange={sort => {
                          this.ordering = sort as string;
                        }}
                      />
                    </div>
                  </div>
                );
              },
            }}
            initialDivide={208}
            isCollapsed={this.isCollapsed}
            maxWidth={500}
            minWidth={160}
            onUpdate:isCollapsed={this.updateIsCollapsed}
          />
        </div>
      </div>
    );
  },
});
