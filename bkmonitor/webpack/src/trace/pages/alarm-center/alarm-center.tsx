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
import { computed, defineComponent, onBeforeMount, shallowRef, watchEffect } from 'vue';

import { tryURLDecodeParse } from 'monitor-common/utils';
import { useRoute, useRouter } from 'vue-router';

import { EMode } from '../../components/retrieval-filter/typing';
import { mergeWhereList } from '../../components/retrieval-filter/utils';
import { getDefaultTimezone } from '../../i18n/dayjs';
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
import { type CommonCondition, AlarmType, CONTENT_SCROLL_ELEMENT_CLASS_NAME } from './typings';
import { useAlarmCenterStore } from '@/store/modules/alarm-center';

import './alarm-center.scss';
export default defineComponent({
  name: 'AlarmCenter',
  setup() {
    const router = useRouter();
    const route = useRoute();
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

    const handleConditionChange = (condition: CommonCondition) => {
      alarmStore.conditions = mergeWhereList(alarmStore.conditions, [
        {
          ...condition,
          ...(alarmStore.conditions.length > 1 ? { condition: 'and' } : {}),
        },
      ]);
    };

    const retrievalFilterFields = computed(() => {
      return alarmStore.alarmService.filterFields;
    });

    watchEffect(() => {
      setUrlParams();
    });

    function setUrlParams() {
      const queryParams = {
        from: alarmStore.timeRange[0],
        to: alarmStore.timeRange[1],
        timezone: alarmStore.timezone,
        refreshInterval: String(alarmStore.refreshInterval),
        queryString: alarmStore.queryString,
        conditions: JSON.stringify(alarmStore.conditions),
        residentCondition: JSON.stringify(alarmStore.residentCondition),
        quickFilterValue: JSON.stringify(alarmStore.quickFilterValue),
        filterMode: alarmStore.filterMode,
        alarmType: alarmStore.alarmType,
        bizIds: JSON.stringify(alarmStore.bizIds),
      };

      const targetRoute = router.resolve({
        query: queryParams,
      });
      // /** 防止出现跳转当前地址导致报错 */
      if (targetRoute.fullPath !== route.fullPath) {
        router.replace({
          query: queryParams,
        });
      }
    }

    function getUrlParams() {
      const {
        from,
        to,
        timezone,
        refreshInterval,
        queryString,
        conditions,
        residentCondition,
        quickFilterValue,
        filterMode,
        bizIds,
        alarmType,
      } = route.query;
      try {
        if (from && to) {
          alarmStore.timeRange = [from as string, to as string];
        }
        alarmStore.timezone = (timezone as string) || getDefaultTimezone();
        alarmStore.refreshInterval = Number(refreshInterval) || -1;
        alarmStore.queryString = (queryString as string) || '';
        alarmStore.conditions = tryURLDecodeParse(conditions as string, []);
        alarmStore.residentCondition = tryURLDecodeParse(residentCondition as string, []);
        alarmStore.quickFilterValue = tryURLDecodeParse(quickFilterValue as string, []);
        alarmStore.filterMode = (filterMode as EMode) || EMode.ui;
        alarmStore.bizIds = tryURLDecodeParse(bizIds as string, [-1]);
        alarmStore.alarmType = (alarmType as AlarmType) || AlarmType.ALERT;
      } catch (error) {
        console.log('route query:', error);
      }
    }

    onBeforeMount(() => {
      getUrlParams();
      setUrlParams();
    });

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
      retrievalFilterFields,
      handleFilterValueChange,
      updateIsCollapsed,
      handleConditionChange,
    };
  },
  render() {
    return (
      <div class='alarm-center'>
        <AlarmCenterHeader class='alarm-center-header' />
        <AlarmRetrievalFilter
          class='alarm-center-filters'
          fields={this.retrievalFilterFields}
        />
        <div class='alarm-center-main'>
          <TraceExploreLayout
            class='alarm-center-layout'
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
                      <AlarmAnalysis onConditionChange={this.handleConditionChange} />
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
