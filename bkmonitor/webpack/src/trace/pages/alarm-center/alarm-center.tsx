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

import { EFieldType, EMode } from '../../components/retrieval-filter/typing';
import { mergeWhereList } from '../../components/retrieval-filter/utils';
import useUserConfig from '../../hooks/useUserConfig';
import { getDefaultTimezone } from '../../i18n/dayjs';
import TraceExploreLayout from '../trace-explore/components/trace-explore-layout';
import AlarmCenterDetail from './alarm-detail/alarm-detail-sideslider';
import AlarmAnalysis from './components/alarm-analysis/alarm-analysis';
import AlarmCenterHeader from './components/alarm-center-header';
import AlarmRetrievalFilter from './components/alarm-retrieval-filter/alarm-retrieval-filter';
import { useAlarmFilter } from './components/alarm-retrieval-filter/hooks/use-alarm-filter';
import AlarmTable from './components/alarm-table/alarm-table';
import AlarmTrendChart from './components/alarm-trend-chart/alarm-trend-chart';
import QuickFiltering from './components/quick-filtering';
import { useAlarmTable } from './composables/use-alarm-table';
import { useQuickFilter } from './composables/use-quick-filter';
import { useAlarmTableColumns } from './composables/use-table-columns';
import { type CommonCondition, AlarmType, CONTENT_SCROLL_ELEMENT_CLASS_NAME } from './typings';
import { useAlarmCenterStore } from '@/store/modules/alarm-center';
import { useAppStore } from '@/store/modules/app';

import './alarm-center.scss';
export default defineComponent({
  name: 'AlarmCenter',
  setup() {
    const router = useRouter();
    const route = useRoute();
    const alarmStore = useAlarmCenterStore();
    const appStore = useAppStore();
    const {
      handleGetUserConfig: handleGetResidentSettingUserConfig,
      handleSetUserConfig: handleSetResidentSettingUserConfig,
    } = useUserConfig();
    const { quickFilterList, quickFilterLoading } = useQuickFilter();
    const { data, loading, total, page, pageSize, ordering } = useAlarmTable();
    const {
      tableColumns: tableSourceColumns,
      storageColumns,
      allTableFields,
      lockedTableFields,
    } = useAlarmTableColumns();

    const isCollapsed = shallowRef(false);
    const alarmId = shallowRef<string>('');
    const alarmDetailShow = shallowRef(false);
    /**
     * @description 检索栏字段列表
     */
    const retrievalFilterFields = computed(() => {
      const filterFields = [...alarmStore.alarmService.filterFields];
      const spliceIndex = filterFields.findIndex(item => item.name === 'tags');
      if (spliceIndex !== -1) {
        filterFields.splice(
          spliceIndex,
          1,
          ...alarmStore.dimensionTags.map(item => ({
            name: item.id,
            alias: item.name,
            methods: [
              {
                alias: '=',
                value: 'eq',
              },
              {
                alias: '!=',
                value: 'neq',
              },
            ],
            isEnableOptions: true,
            type: EFieldType.keyword,
          }))
        );
      }
      return filterFields;
    });
    /**
     * @description 检索栏收藏列表
     */
    const favoriteList = computed(() => {
      return (
        alarmStore.favoriteList.map(item => ({
          groupName: '',
          id: item.id,
          name: item.name,
          config: {
            queryString: item?.params?.query_string || '',
            where: [],
            commonWhere: [],
          },
        })) || []
      );
    });
    /**
     * @description 检索栏常驻设置唯一id
     */
    const residentSettingOnlyId = computed(() => {
      return `ALARM_CENTER_RESIDENT_SETTING__${alarmStore.alarmType}`;
    });

    const updateIsCollapsed = (v: boolean) => {
      isCollapsed.value = v;
    };

    const handleFilterValueChange = (filterValue: CommonCondition[]) => {
      alarmStore.quickFilterValue = filterValue;
    };

    const handleAddCondition = (condition: CommonCondition) => {
      console.log(condition);
      if (alarmStore.filterMode === EMode.ui) {
        alarmStore.conditions = mergeWhereList(alarmStore.conditions, [
          {
            key: condition.key,
            method: condition.method,
            value: condition.value.map(item => {
              if (item.startsWith('"') && item.endsWith('"')) {
                return item.slice(1, -1);
              }
              return item;
            }),
            ...(alarmStore.conditions.length > 1 ? { condition: 'and' } : {}),
          },
        ]);
      } else {
        const queryString = `${alarmStore.queryString ? ' AND ' : ''}${condition.method === 'neq' ? '-' : ''}${condition.key}: ${condition.value[0]}`;
        alarmStore.queryString = queryString;
      }
    };
    function handleConditionChange(condition: CommonCondition[]) {
      alarmStore.conditions = condition;
    }
    function handleQueryStringChange(queryString: string) {
      alarmStore.queryString = queryString;
    }
    function handleFilterModeChange(mode: EMode) {
      alarmStore.filterMode = mode;
    }
    function handleResidentConditionChange(condition: CommonCondition[]) {
      alarmStore.residentCondition = condition;
    }
    function handleQuery() {
      alarmStore.refreshImmediate += 1;
    }
    function handleBizIdsChange(bizIds: (number | string)[]) {
      alarmStore.bizIds = bizIds as number[];
    }

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
        currentPage: page.value,
        sortOrder: ordering.value,
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
        sortOrder,
        currentPage,
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
        ordering.value = (sortOrder as string) || '';
        page.value = Number(currentPage || 1);
      } catch (error) {
        console.log('route query:', error);
      }
    }

    /**
     * @description 表格 -- 处理分页变化
     */
    function handleCurrentPageChange(currentPage: number) {
      page.value = currentPage;
      setUrlParams();
    }
    /**
     * @description 表格 -- 处理分页大小变化
     */
    function handlePageSizeChange(size: number) {
      pageSize.value = size;
      handleCurrentPageChange(1);
    }
    /**
     * @description 表格 -- 处理排序变化
     */
    function handleSortChange(sort: string) {
      ordering.value = sort;
      handleCurrentPageChange(1);
    }

    /**
     * 展示告警详情
     */
    function handleShowAlertDetail(id: string) {
      alarmId.value = id;
      handleDetailShowChange(true);
    }

    /**  展示处理记录详情  */
    function handleShowActionDetail(_id: string) {
      handleDetailShowChange(true);
    }

    function handleDetailShowChange(show: boolean) {
      alarmDetailShow.value = show;
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
      appStore,
      retrievalFilterFields,
      favoriteList,
      residentSettingOnlyId,
      alarmId,
      alarmDetailShow,
      handleFilterValueChange,
      updateIsCollapsed,
      handleAddCondition,
      handleConditionChange,
      handleQueryStringChange,
      handleFilterModeChange,
      handleResidentConditionChange,
      handleQuery,
      handleBizIdsChange,
      handleCurrentPageChange,
      handlePageSizeChange,
      handleSortChange,
      handleGetResidentSettingUserConfig,
      handleSetResidentSettingUserConfig,
      handleShowAlertDetail,
      handleShowActionDetail,
      ...useAlarmFilter({
        alarmType: alarmStore.alarmType,
        commonFilterParams: alarmStore.commonFilterParams,
        filterMode: alarmStore.filterMode,
      }),
      handleDetailShowChange,
    };
  },
  render() {
    return (
      <div class='alarm-center'>
        <AlarmCenterHeader class='alarm-center-header' />
        <AlarmRetrievalFilter
          class='alarm-center-filters'
          bizIds={this.alarmStore.bizIds}
          bizList={this.appStore.bizList}
          conditions={this.alarmStore.conditions}
          favoriteList={this.favoriteList}
          fields={this.retrievalFilterFields}
          filterMode={this.alarmStore.filterMode}
          getValueFn={this.getRetrievalFilterValueData}
          handleGetUserConfig={this.handleGetResidentSettingUserConfig}
          handleSetUserConfig={this.handleSetResidentSettingUserConfig}
          needIncidentOption={this.alarmStore.alarmType === AlarmType.INCIDENT}
          queryString={this.alarmStore.queryString}
          residentCondition={this.alarmStore.residentCondition}
          residentSettingOnlyId={this.residentSettingOnlyId}
          onBizIdsChange={this.handleBizIdsChange}
          onConditionChange={this.handleConditionChange}
          onFilterModeChange={this.handleFilterModeChange}
          onQuery={this.handleQuery}
          onQueryStringChange={this.handleQueryStringChange}
          onResidentConditionChange={this.handleResidentConditionChange}
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
                      <AlarmAnalysis onConditionChange={this.handleAddCondition} />
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
                        onCurrentPageChange={this.handleCurrentPageChange}
                        onDisplayColFieldsChange={displayColFields => {
                          this.storageColumns = displayColFields;
                        }}
                        onPageSizeChange={this.handlePageSizeChange}
                        onShowActionDetail={this.handleShowActionDetail}
                        onShowAlertDetail={this.handleShowAlertDetail}
                        onSortChange={sort => this.handleSortChange(sort as string)}
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

        <AlarmCenterDetail
          alarmId={this.alarmId}
          show={this.alarmDetailShow}
          onUpdate:show={this.handleDetailShowChange}
        />
      </div>
    );
  },
});
