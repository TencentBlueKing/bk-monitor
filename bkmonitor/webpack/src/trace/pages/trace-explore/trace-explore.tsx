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
import { computed, defineComponent, onMounted, shallowRef, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import { useDebounceFn } from '@vueuse/core';
import { listApplicationInfo } from 'monitor-api/modules/apm_meta';
import { random } from 'monitor-common/utils';

import RetrievalFilter from '../../components/retrieval-filter/retrieval-filter';
import { ECondition, EMode } from '../../components/retrieval-filter/typing';
import { mergeWhereList } from '../../components/retrieval-filter/utils';
import { DEFAULT_TIME_RANGE } from '../../components/time-range/utils';
import { useTraceExploreStore } from '../../store/modules/explore';
import DimensionFilterPanel from './components/dimension-filter-panel';
import TraceExploreHeader from './components/trace-explore-header';
import TraceExploreLayout from './components/trace-explore-layout';
import TraceExploreView from './components/trace-explore-view/trace-explore-view';

import type { ConditionChangeEvent, IApplicationItem, ICommonParams } from './typing';

import './trace-explore.scss';
export default defineComponent({
  name: 'TraceExplore',
  props: {},
  setup() {
    const route = useRoute();
    const router = useRouter();
    const traceExploreLayoutRef = shallowRef<InstanceType<typeof traceExploreLayoutRef>>();
    const store = useTraceExploreStore();

    /** 应用列表 */
    const applicationList = shallowRef<IApplicationItem[]>([]);
    /** 是否展示收藏夹 */
    const isShowFavorite = shallowRef(true);

    function handleFavoriteShowChange(isShow: boolean) {
      isShowFavorite.value = isShow;
    }
    const filterMode = shallowRef<EMode>(EMode.ui);

    const where = shallowRef([]);
    /** 常驻筛选 */
    const commonWhere = shallowRef([]);
    /** 是否展示常驻筛选 */
    const showResidentBtn = shallowRef(false);
    /** 不同视角下维度字段的列表 */
    const fieldListMap = shallowRef({ trace: [], span: [] });
    /** 维度字段列表 */
    const fieldList = computed(() => {
      return store.mode === 'trace' ? fieldListMap.value.trace : fieldListMap.value.span;
    });

    const commonParams = shallowRef<ICommonParams>({
      app_name: '',
      query_string: '',
      filters: [],
      mode: 'trace',
    });

    const loading = shallowRef(false);
    const queryString = shallowRef('');

    const residentSettingOnlyId = computed(() => {
      const RESIDENT_SETTING = 'TRACE_RESIDENT_SETTING';
      return `${store.mode}_${store.appName}_${RESIDENT_SETTING}`;
    });

    watch(
      [
        () => store.appName,
        () => store.timeRange,
        () => store.refreshImmediate,
        () => store.mode,
        () => store.refreshInterval,
      ],
      async (val, oldVal) => {
        if (val[0] !== oldVal[0]) {
          await getViewConfig();
        }
        handleQuery();
      }
    );

    async function getApplicationList() {
      const data = await listApplicationInfo().catch(() => []);
      applicationList.value = data;
      store.updateAppList(data);
      if (!store.appName || !data.find(item => item.app_name === store.appName)) {
        store.updateAppName(data[0]?.app_name);
      }
    }

    function handleCloseDimensionPanel() {
      traceExploreLayoutRef.value.handleClickShrink(false);
    }

    function handleConditionChange(item: ConditionChangeEvent) {
      const { key, method, value } = item;
      if (filterMode.value === EMode.ui) {
        where.value = mergeWhereList(where.value, [{ condition: ECondition.and, key, method, value: [value || ''] }]);
      } else {
      }
      handleQuery();
    }

    const handleQuery = useDebounceFn(() => {
      let query_string = '';
      let filters = mergeWhereList(where.value || [], commonWhere.value || []);
      if (filterMode.value === EMode.ui) {
        // 全文检索补充到query_string里
        const fullText = filters.find(item => item.key === '*');
        query_string = fullText?.value[0] ? `"${fullText?.value[0]}"` : '';
        filters = filters.filter(item => item.key !== '*');
      } else {
        query_string = queryString.value;
        filters = [];
      }

      commonParams.value = {
        app_name: store.appName,
        mode: store.mode,
        query_string,
        filters,
      };
    }, 100);

    async function getViewConfig() {
      function mock(params) {
        console.log(params);
        return new Promise(resolve => {
          setTimeout(() => {
            resolve({
              trace_config: {
                fields: [
                  {
                    name: 'trace_duration',
                    alias: '耗时',
                    type: 'date',
                    is_searched: true,
                    is_dimensions: true,
                    is_option_enabled: true,
                    can_displayed: true,
                    is_default_filter: true,
                  },
                  {
                    name: 'time',
                    alias: '数据上报时间',
                    type: 'date',
                    is_searched: true,
                    is_dimensions: true,
                    is_option_enabled: false,
                    supported_operations: [{ operator: '=', label: '=', placeholder: '请选择或直接输入，Enter分隔' }],
                  },
                  {
                    name: 'trace_id',
                    alias: 'Trace ID',
                    type: 'keyword',
                    is_searched: true,
                    is_dimensions: true,
                    is_option_enabled: false,
                    supported_operations: [{ operator: '=', label: '=', placeholder: '请选择或直接输入，Enter分隔' }],
                  },
                  {
                    name: 'root_service_category',
                    alias: '调用类型',
                    type: 'keyword',
                    is_searched: true,
                    is_dimensions: true,
                    is_option_enabled: true,
                    can_displayed: true,
                    is_default_filter: true,
                  },
                  {
                    name: 'number',
                    alias: '数值',
                    type: 'integer',
                    is_searched: true,
                    is_dimensions: true,
                    is_option_enabled: true,
                    can_displayed: true,
                    is_default_filter: true,
                  },
                ],
              },
              span_config: {
                fields: [
                  {
                    name: 'time',
                    alias: '数据上报时间',
                    type: 'date',
                    is_searched: true,
                    is_dimensions: true,
                    is_option_enabled: true,
                    can_displayed: true,
                    supported_operations: [
                      {
                        operator: '=',
                        label: '=',
                        placeholder: '请选择或直接输入，Enter分隔',
                      },
                    ],
                  },
                ],
              },
            });
          }, 300);
        });
      }
      // if (!store.appName) return;
      const data = await mock({
        app_name: store.appName,
      });
      fieldListMap.value = {
        trace: data.trace_config.fields,
        span: data.span_config.fields,
      };
    }

    onMounted(async () => {
      getUrlParams();
      await getApplicationList();
      setUrlParams();
    });

    function getUrlParams() {
      const {
        start_time,
        end_time,
        timezone,
        refreshInterval,
        sceneMode,
        app_name,
        filterMode: queryFilterMode,
        where: queryWhere,
        commonWhere: queryCommonWhere,
        showResidentBtn: queryShowResidentBtn,
        queryString: queryQueryString,
      } = route.query;
      try {
        store.init({
          timeRange: start_time ? [start_time as string, end_time as string] : DEFAULT_TIME_RANGE,
          timezone: timezone as string,
          mode: (sceneMode as 'span' | 'trace') || 'trace',
          appName: app_name as string,
          refreshInterval: Number(refreshInterval) || -1,
          refreshImmediate: random(3),
        });
        where.value = JSON.parse((queryWhere as string) || '[]');
        commonWhere.value = JSON.parse((queryCommonWhere as string) || '[]');
        showResidentBtn.value = Boolean(queryShowResidentBtn);
        queryString.value = queryQueryString as string;
        filterMode.value = (queryFilterMode as EMode) || EMode.ui;
      } catch (error) {
        console.log('route query:', error);
      }
    }

    function setUrlParams() {
      const query = {
        ...route.query,
        from: store.timeRange[0],
        to: store.timeRange[1],
        timezone: store.timezone,
        refreshInterval: String(store.refreshInterval),
        sceneMode: store.mode,
        app_name: store.appName,
        queryString: queryString.value,
        where: JSON.stringify(where.value),
        commonWhere: JSON.stringify(commonWhere.value),
        showResidentBtn: String(showResidentBtn.value),
        filterMode: filterMode.value,
      };

      const targetRoute = router.resolve({
        query,
      });
      // /** 防止出现跳转当前地址导致报错 */
      if (targetRoute.fullPath !== route.fullPath) {
        router.replace({
          query,
        });
      }
    }

    return {
      traceExploreLayoutRef,
      applicationList,
      isShowFavorite,
      where,
      fieldList,
      commonParams,
      loading,
      queryString,
      residentSettingOnlyId,
      handleFavoriteShowChange,
      handleCloseDimensionPanel,
      handleConditionChange,
    };
  },
  render() {
    return (
      <div class='trace-explore'>
        <div class='favorite-panel' />
        <div class='main-panel'>
          <div class='header-panel'>
            <TraceExploreHeader
              isShowFavorite={this.isShowFavorite}
              list={this.applicationList}
              onFavoriteShowChange={this.handleFavoriteShowChange}
            />
          </div>
          <div class='trace-explore-content'>
            {this.loading ? (
              <div class='skeleton-element filter-skeleton' />
            ) : (
              <RetrievalFilter
                fields={this.fieldList}
                residentSettingOnlyId={this.residentSettingOnlyId}
              />
            )}
            <TraceExploreLayout
              ref='traceExploreLayoutRef'
              class='content-container'
            >
              {{
                aside: () => (
                  <div class='dimension-filter-panel'>
                    <DimensionFilterPanel
                      list={this.fieldList}
                      listLoading={this.loading}
                      params={this.commonParams}
                      onClose={this.handleCloseDimensionPanel}
                      onConditionChange={this.handleConditionChange}
                    />
                  </div>
                ),
                default: () => (
                  <div class='result-content-panel'>
                    <TraceExploreView commonParams={this.commonParams} />
                  </div>
                ),
              }}
            </TraceExploreLayout>
          </div>
        </div>
      </div>
    );
  },
});
