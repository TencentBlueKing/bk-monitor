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
import { computed, defineComponent, onBeforeUnmount, onMounted, shallowRef, useTemplateRef, watch } from 'vue';

import { useI18n } from 'vue-i18n';
import { useRoute } from 'vue-router';

import RetrievalFilter from '../../components/retrieval-filter/retrieval-filter';
import { traceWhereChangeFormatter, traceWhereFormatter } from '../../components/retrieval-filter/utils';
import useUserConfig from '../../hooks/useUserConfig';
import { updateTimezone } from '../../i18n/dayjs';
import { useRumExploreStore } from '../../store/modules/rum-explore';
import FavoriteBox, { EditFavorite } from '../trace-explore/components/favorite-box';
import TraceExploreLayout from '../trace-explore/components/trace-explore-layout';
import RumDimensionPanel from './components/rum-dimension-panel';
import RumExploreHeader from './components/rum-explore-header';
import RumExploreTable from './components/rum-explore-table';
import RumExploreView from './components/rum-explore-view/rum-explore-view';
import RumSpanTypeFilter from './components/rum-span-type-filter';
import {
  useRumFavorite,
  useRumFieldValues,
  useRumQuery,
  useRumSpanType,
  useRumTableData,
  useRumViewConfig,
} from './composables';
import { RUM_RESIDENT_SETTING_KEY } from './constants';
import { getApplicationList } from './services/rum-application';

import type { IRumApplication } from './typings';

import './rum-explore.scss';

/** 默认应用与置顶应用的用户配置 key */
const RUM_EXPLORE_DEFAULT_APPLICATION = 'RUM_EXPLORE_DEFAULT_APPLICATION';
const RUM_EXPLORE_APPLICATION_THUMBTACK = 'rum_explore_application_thumbtack';

export default defineComponent({
  name: 'RumExplore',
  setup() {
    const { t } = useI18n();
    const route = useRoute();
    const store = useRumExploreStore();

    const { handleGetUserConfig: getDefaultAppConfig, handleSetUserConfig: setDefaultAppConfig } = useUserConfig();
    const { handleGetUserConfig: getThumbtackConfig, handleSetUserConfig: setThumbtackConfig } = useUserConfig();
    const { handleGetUserConfig: getResidentConfig, handleSetUserConfig: setResidentConfig } = useUserConfig();

    const isCollapsed = shallowRef(false);
    const applicationList = shallowRef<IRumApplication[]>([]);
    const thumbtackList = shallowRef<string[]>([]);
    const defaultApplication = shallowRef('');
    /** 表格当前展示的列 */
    const displayFields = shallowRef<string[]>([]);

    const viewConfigCtx = useRumViewConfig();
    const spanTypeCtx = useRumSpanType(viewConfigCtx.viewConfig);
    const queryCtx = useRumQuery({ extraFilters: spanTypeCtx.spanTypeFilters });
    const tableCtx = useRumTableData(queryCtx.commonParams);
    const { getFieldValues } = useRumFieldValues(computed(() => viewConfigCtx.viewConfig.value.fields));

    const favoriteBoxRef = useTemplateRef<InstanceType<typeof FavoriteBox>>('favoriteBoxRef');
    const favoriteCtx = useRumFavorite({
      where: queryCtx.where,
      commonWhere: queryCtx.commonWhere,
      queryString: queryCtx.queryString,
      filterMode: queryCtx.filterMode,
      displayFields,
      onApplied: () => queryCtx.handleQuery(),
    });

    // URL 状态要在应用列表加载前恢复，否则会被默认应用覆盖
    queryCtx.initFromUrl();

    const isSpanMode = computed(() => store.mode === 'span');
    const residentSettingOnlyId = computed(() => `${RUM_RESIDENT_SETTING_KEY}_${store.mode}_${store.appName}`);
    const favoriteList = computed(
      () =>
        favoriteBoxRef.value?.getFavoriteList()?.map(item => ({
          ...item,
          config: {
            queryString: item?.config?.queryParams?.query || '',
            where: item?.config?.queryParams?.filters || [],
            commonWhere: item?.config?.componentData?.commonWhere || [],
          },
        })) || []
    );

    /** 切换 span 类型后表格列跟着换成该类型的默认列 */
    watch(
      () => spanTypeCtx.spanTypeDisplayFields.value,
      fields => {
        displayFields.value = [...fields];
      },
      { immediate: true }
    );

    watch(
      () => store.timezone,
      timezone => updateTimezone(timezone)
    );

    /** 自动刷新 */
    let autoRefreshTimer: number = null;
    watch(
      () => store.refreshInterval,
      interval => {
        window.clearInterval(autoRefreshTimer);
        if (!(interval > 0)) return;
        autoRefreshTimer = window.setInterval(() => tableCtx.fetchList(), interval);
      },
      { immediate: true }
    );

    async function fetchApplicationList() {
      const list = await getApplicationList();
      applicationList.value = list;
      store.appList = list;
      if (store.appName && list.some(item => item.app_name === store.appName)) return;
      const preferred = defaultApplication.value || thumbtackList.value[0];
      store.appName = list.some(item => item.app_name === preferred) ? preferred : list[0]?.app_name || '';
    }

    async function fetchUserConfig() {
      await Promise.all([
        getDefaultAppConfig<string>(RUM_EXPLORE_DEFAULT_APPLICATION).then(res => {
          defaultApplication.value = res || '';
        }),
        getThumbtackConfig<string[]>(RUM_EXPLORE_APPLICATION_THUMBTACK).then(res => {
          thumbtackList.value = res || [];
        }),
      ]);
    }

    function handleAppNameChange() {
      queryCtx.where.value = [];
      queryCtx.commonWhere.value = [];
      setDefaultAppConfig(JSON.stringify(store.appName));
      queryCtx.handleQuery();
    }

    function handleModeChange() {
      queryCtx.handleQuery();
    }

    function handleSpanTypeChange(type: string) {
      spanTypeCtx.setSpanType(type);
      queryCtx.handleQuery();
    }

    async function handleThumbtackChange(list: string[]) {
      thumbtackList.value = list;
      await setThumbtackConfig(JSON.stringify(list));
    }

    /** 维度面板与表格单元格触发的条件追加 */
    function handleConditionChange(condition: { key: string; method: string; value: string }) {
      queryCtx.addCondition({ key: condition.key, operator: condition.method, value: [condition.value] }, true);
    }

    function handleSortChange(sort: string | string[]) {
      tableCtx.handleSortChange(sort);
      queryCtx.setUrlParams();
    }

    onMounted(async () => {
      updateTimezone(store.timezone);
      await fetchUserConfig();
      await fetchApplicationList();
      queryCtx.handleQuery();
    });

    onBeforeUnmount(() => {
      window.clearInterval(autoRefreshTimer);
    });

    return {
      t,
      route,
      store,
      applicationList,
      displayFields,
      favoriteBoxRef,
      favoriteCtx,
      favoriteList,
      isCollapsed,
      isSpanMode,
      queryCtx,
      residentSettingOnlyId,
      spanTypeCtx,
      tableCtx,
      thumbtackList,
      viewConfigCtx,
      getFieldValues,
      getResidentConfig,
      setResidentConfig,
      handleAppNameChange,
      handleConditionChange,
      handleModeChange,
      handleSortChange,
      handleSpanTypeChange,
      handleThumbtackChange,
    };
  },
  render() {
    const { favoriteCtx, queryCtx, spanTypeCtx, tableCtx, viewConfigCtx } = this;

    return (
      <div class='rum-explore'>
        <div
          style={{ display: favoriteCtx.favoriteShow.value ? 'block' : 'none' }}
          class='favorite-panel'
        >
          <FavoriteBox
            ref='favoriteBoxRef'
            defaultFavoriteId={queryCtx.urlFavoriteId.value}
            type='rum'
            onChange={favoriteCtx.applyFavorite}
            onClose={() => {
              favoriteCtx.favoriteShow.value = false;
            }}
            onOpenBlank={data => favoriteCtx.openFavoriteInBlank(data, this.route.path)}
          />
        </div>

        <div class='main-panel'>
          <RumExploreHeader
            applicationList={this.applicationList}
            favoriteShow={favoriteCtx.favoriteShow.value}
            thumbtackList={this.thumbtackList}
            onAppNameChange={this.handleAppNameChange}
            onFavoriteShowChange={show => {
              favoriteCtx.favoriteShow.value = show;
            }}
            onModeChange={this.handleModeChange}
            onThumbtackChange={this.handleThumbtackChange}
          />

          <div class='rum-explore-content'>
            {viewConfigCtx.loading.value ? (
              <div class='skeleton-element filter-skeleton' />
            ) : (
              <RetrievalFilter
                changeWhereFormatter={traceWhereChangeFormatter}
                commonWhere={queryCtx.commonWhere.value}
                copyLoading={queryCtx.generateQueryStringLoading.value}
                defaultShowResidentBtn={queryCtx.showResidentBtn.value}
                favoriteList={this.favoriteList}
                fields={viewConfigCtx.retrievalFields.value}
                filterMode={queryCtx.filterMode.value}
                getValueFn={this.getFieldValues}
                handleGetUserConfig={this.getResidentConfig}
                handleSetUserConfig={this.setResidentConfig}
                isShowClear={true}
                isShowCopy={true}
                isShowFavorite={true}
                isShowResident={true}
                modeChangeLoading={queryCtx.generateQueryStringLoading.value}
                queryString={queryCtx.queryString.value}
                residentSettingOnlyId={this.residentSettingOnlyId}
                selectFavorite={favoriteCtx.selectedFavorite.value}
                where={queryCtx.where.value}
                whereFormatter={traceWhereFormatter}
                onCommonWhereChange={value => {
                  queryCtx.commonWhere.value = value;
                  queryCtx.handleQuery();
                }}
                onCopyWhere={queryCtx.copyWhere}
                onFavorite={isEdit => favoriteCtx.saveFavorite(isEdit, () => this.favoriteBoxRef?.refreshGroupList())}
                onModeChange={queryCtx.modeChange}
                onQueryStringChange={value => {
                  queryCtx.queryString.value = value;
                }}
                onSearch={queryCtx.handleQuery}
                onShowResidentBtnChange={value => {
                  queryCtx.showResidentBtn.value = value;
                }}
                onWhereChange={queryCtx.whereChange}
              />
            )}

            {this.isSpanMode ? (
              <TraceExploreLayout
                isCollapsed={this.isCollapsed}
                onUpdate:isCollapsed={value => {
                  this.isCollapsed = value;
                }}
              >
                {{
                  aside: () => (
                    <RumDimensionPanel
                      activeSpanType={spanTypeCtx.activeSpanType.value}
                      commonParams={queryCtx.commonParams.value}
                      groups={viewConfigCtx.fieldGroups.value}
                      loading={viewConfigCtx.loading.value}
                      timeRange={this.store.timeRange}
                      onClose={() => {
                        this.isCollapsed = true;
                      }}
                      onConditionChange={this.handleConditionChange}
                    />
                  ),
                  default: () => (
                    <div class='result-panel'>
                      <RumExploreView
                        v-slots={{
                          affixedTop: () => (
                            <RumSpanTypeFilter
                              list={spanTypeCtx.chipList.value}
                              value={spanTypeCtx.activeSpanType.value}
                              onChange={this.handleSpanTypeChange}
                            />
                          ),
                          default: () => (
                            <RumExploreTable
                              commonParams={queryCtx.commonParams.value}
                              data={tableCtx.tableData.value}
                              displayableFields={viewConfigCtx.displayableFields.value}
                              displayFields={this.displayFields}
                              hasMore={tableCtx.hasMore.value}
                              loading={tableCtx.loading.value}
                              mode={this.store.mode}
                              scrollLoading={tableCtx.scrollLoading.value}
                              sort={this.store.sortParams}
                              timeRange={this.store.timeRange}
                              onClearFilter={queryCtx.clearQuery}
                              onConditionChange={this.handleConditionChange}
                              onDisplayFieldChange={fields => {
                                this.displayFields = fields;
                              }}
                              onScrollToEnd={tableCtx.handleScrollToEnd}
                              onSortChange={this.handleSortChange}
                            />
                          ),
                        }}
                        backTopSignal={tableCtx.backTopSignal.value}
                      />
                    </div>
                  ),
                }}
              </TraceExploreLayout>
            ) : (
              // Session / View 视角本期不实现，先留空占位
              <div class='rum-explore-mode-placeholder' />
            )}
          </div>
        </div>

        <EditFavorite
          data={favoriteCtx.editFavoriteData.value}
          isCreate={true}
          isShow={favoriteCtx.editFavoriteShow.value}
          onClose={() => {
            favoriteCtx.editFavoriteShow.value = false;
          }}
          onSuccess={() => {
            favoriteCtx.editFavoriteShow.value = false;
          }}
        />
      </div>
    );
  },
});
