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
import { computed, defineComponent, ref as deepRef, onMounted, shallowRef, watch, onUnmounted } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import { useDebounceFn } from '@vueuse/core';
import { listApplicationInfo } from 'monitor-api/modules/apm_meta';
import { getFieldsOptionValues, listTraceViewConfig } from 'monitor-api/modules/apm_trace';
import { random } from 'monitor-common/utils';
import pinyin from 'tiny-pinyin';

import RetrievalFilter from '../../components/retrieval-filter/retrieval-filter';
import { EMode, type IWhereItem, type IGetValueFnParams, EMethod } from '../../components/retrieval-filter/typing';
import {
  mergeWhereList,
  SPAN_DEFAULT_RESIDENT_SETTING_KEY,
  TRACE_DEFAULT_RESIDENT_SETTING_KEY,
} from '../../components/retrieval-filter/utils';
import { DEFAULT_TIME_RANGE, handleTransformToTimestamp } from '../../components/time-range/utils';
import { useTraceExploreStore } from '../../store/modules/explore';
import DimensionFilterPanel from './components/dimension-filter-panel';
import FavoriteBox from './components/favorite-box';
import TraceExploreHeader from './components/trace-explore-header';
import TraceExploreLayout from './components/trace-explore-layout';
import TraceExploreView from './components/trace-explore-view/trace-explore-view';
import { getFilterByCheckboxFilter } from './utils';

import type { ConditionChangeEvent, ExploreFieldMap, IApplicationItem, ICommonParams, IDimensionField } from './typing';

import './trace-explore.scss';
export default defineComponent({
  name: 'TraceExplore',
  props: {},
  setup() {
    const route = useRoute();
    const router = useRouter();
    const traceExploreLayoutRef = shallowRef<InstanceType<typeof traceExploreLayoutRef>>();
    const store = useTraceExploreStore();

    /** 自动查询定时器 */
    let autoQueryTimer = null;
    /** 应用列表 */
    const applicationList = shallowRef<IApplicationItem[]>([]);
    /** 是否展示收藏夹 */
    const isShowFavorite = shallowRef(true);
    /** 视角切换查询 */
    const cacheSceneQuery = new Map<string, Record<string, any>>();

    function handleFavoriteShowChange(isShow: boolean) {
      isShowFavorite.value = isShow;
    }
    const filterMode = shallowRef<EMode>(EMode.ui);

    const where = shallowRef<IWhereItem[]>([]);
    /** 常驻筛选 */
    const commonWhere = shallowRef<IWhereItem[]>([]);
    /** 是否展示常驻筛选 */
    const showResidentBtn = shallowRef(false);
    /** 不同视角下维度字段的列表 */
    const fieldListMap = shallowRef<{ trace: IDimensionField[]; span: IDimensionField[] }>({ trace: [], span: [] });
    /** table上方快捷筛选操作区域（ “包含” 区域中的 复选框组）选中的值 */
    const checkboxFilters = deepRef([]);
    /** 维度字段列表 */
    const fieldList = computed(() => {
      return store.mode === 'trace' ? fieldListMap.value.trace : fieldListMap.value.span;
    });
    /** 字段类型 field 映射集合，用于在表格 列配置setting 中获取字段的类型 */
    const fieldMap = computed<ExploreFieldMap>(() => {
      const getFieldMap = (mode: 'span' | 'trace') =>
        fieldListMap.value?.[mode].reduce((prev, curr) => {
          prev[curr.name] = {
            alias: curr.alias,
            name: curr.name,
            type: curr.type,
          };
          return prev;
        }, {});

      return {
        trace: getFieldMap('trace'),
        span: getFieldMap('span'),
      };
    });

    const commonParams = shallowRef<ICommonParams>({
      app_name: '',
      query_string: '',
      filters: [],
      mode: store.mode,
    });

    const loading = shallowRef(false);
    const queryString = shallowRef('');
    const queryStringInput = shallowRef('');

    let axiosController = new AbortController();

    const residentSettingOnlyId = computed(() => {
      const RESIDENT_SETTING = 'TRACE_RESIDENT_SETTING';
      return `${store.mode}_${store.appName}_${RESIDENT_SETTING}`;
    });
    const defaultResidentSetting = computed(() => {
      return store.mode === 'span' ? SPAN_DEFAULT_RESIDENT_SETTING_KEY : TRACE_DEFAULT_RESIDENT_SETTING_KEY;
    });
    const appName = computed(() => store.appName);

    watch(
      () => store.refreshInterval,
      val => {
        autoQueryTimer && clearInterval(autoQueryTimer);
        if (val !== -1) {
          autoQueryTimer = setInterval(() => {
            handleQuery();
          }, val);
        }
      }
    );
    watch(
      () => store.mode,
      () => {
        commonParams.value = {
          ...commonParams.value,
          mode: store.mode,
        };
      }
    );

    /** 视角切换 */
    function handelSceneChange(val: ICommonParams['mode'], oldVal: ICommonParams['mode']) {
      checkboxFilters.value = [];
      cacheSceneQuery.set(
        `${oldVal}_${appName.value}`,
        structuredClone({
          where: where.value,
          query_string: queryString.value,
          commonWhere: commonWhere.value,
        })
      );
      const cacheQuery = cacheSceneQuery.get(`${val}_${appName.value}`);
      where.value = cacheQuery?.where || [];
      queryString.value = cacheQuery?.query_string || '';
      commonWhere.value = cacheQuery?.commonWhere || [];
    }

    /** 应用切换 */
    async function handleAppNameChange() {
      await getViewConfig();
      handleQuery();
    }

    /** 获取应用列表 */
    async function getApplicationList() {
      const data = await listApplicationInfo().catch(() => []);
      applicationList.value = data;
      store.updateAppList(data);
      if (!store.appName || !data.find(item => item.app_name === store.appName)) {
        store.updateAppName(data[0]?.app_name);
      }
    }

    /** 关闭维度列表 */
    function handleCloseDimensionPanel() {
      traceExploreLayoutRef.value.handleClickShrink(false);
    }

    function handleConditionChange(item: ConditionChangeEvent) {
      const { key, method: operator, value } = item;
      if (filterMode.value === EMode.ui) {
        const newWhere = mergeWhereList(where.value, [{ key, operator, value: [value || ''] }]);
        handleWhereChange(newWhere);
        return;
      }
      let endStr = `NOT ${key} : "${value || ''}"`;
      if (operator === EMethod.eq) {
        endStr = `${key} : "${value || ''}"`;
      }
      handleQueryStringChange(queryString.value ? `${queryString.value} AND ${endStr}` : `${endStr}`);
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

      filters = [...filters, ...checkboxFilters.value.map(v => getFilterByCheckboxFilter(store.mode, v))];
      commonParams.value = {
        app_name: store.appName,
        mode: store.mode,
        query_string,
        filters,
      };
      setUrlParams();
    }, 100);

    async function getViewConfig() {
      if (!store.appName) return;
      loading.value = true;
      const { trace_config = [], span_config = [] } = await listTraceViewConfig({
        app_name: store.appName,
      }).catch(() => ({ trace_config: [], span_config: [] }));

      fieldListMap.value = {
        trace: trace_config.map(item => ({ ...item, pinyinStr: pinyin.convertToPinyin(item.alias, '', true) })),
        span: span_config.map(item => ({ ...item, pinyinStr: pinyin.convertToPinyin(item.alias, '', true) })),
      };
      loading.value = false;
    }

    onMounted(async () => {
      getUrlParams();
      await getApplicationList();
      handleQuery();
      await getViewConfig();
    });

    onUnmounted(() => {
      autoQueryTimer && clearInterval(autoQueryTimer);
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
        selectedType,
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
        showResidentBtn.value = JSON.parse((queryShowResidentBtn as string) || 'true');
        queryString.value = queryQueryString as string;
        filterMode.value = (queryFilterMode as EMode) || EMode.ui;
        checkboxFilters.value = JSON.parse((selectedType as string) || '[]');
      } catch (error) {
        console.log('route query:', error);
      }
    }

    function setUrlParams() {
      const query = {
        ...route.query,
        start_time: store.timeRange[0],
        end_time: store.timeRange[1],
        timezone: store.timezone,
        refreshInterval: String(store.refreshInterval),
        sceneMode: store.mode,
        app_name: store.appName,
        queryString: queryString.value,
        where: JSON.stringify(where.value),
        commonWhere: JSON.stringify(commonWhere.value),
        showResidentBtn: String(showResidentBtn.value),
        filterMode: filterMode.value,
        selectedType: JSON.stringify(checkboxFilters.value),
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

    function handleCommonWhereChange(whereP: IWhereItem[]) {
      commonWhere.value = whereP;
      handleQuery();
    }
    function handleWhereChange(whereP: IWhereItem[]) {
      where.value = whereP;
      handleQuery();
    }
    function handleQueryStringChange(val: string) {
      queryString.value = val;
      handleQuery();
    }
    function handleQueryStringInputChange(val: string) {
      queryStringInput.value = val;
    }
    function handleShowResidentBtnChange(val: boolean) {
      showResidentBtn.value = val;
      setUrlParams();
    }
    function handleFilterModeChange(filterModeP: EMode) {
      filterMode.value = filterModeP;
      handleQuery();
    }
    function handleFilterSearch() {
      handleQuery();
    }

    /**
     * @description table上方快捷筛选操作区域（ “包含” 区域中的 复选框组）值改变后回调
     *
     */
    function handleCheckboxFiltersChange(checkboxGroupEvent: string[]) {
      checkboxFilters.value = checkboxGroupEvent;
      handleQuery();
    }

    function getRetrievalFilterValueData(params: IGetValueFnParams) {
      axiosController?.abort?.();
      axiosController = new AbortController();
      const [startTime, endTime] = handleTransformToTimestamp(store.timeRange);
      return getFieldsOptionValues(
        {
          app_name: store.appName,
          start_time: startTime,
          end_time: endTime,
          fields: params?.fields || [],
          limit: params?.limit || 5,
          filters:
            params?.where?.map(item => ({
              key: item.key,
              operator: item.method,
              value: item.value || [],
            })) || [],
          query_string: params?.queryString || '',
          mode: store.mode,
        },
        {
          signal: axiosController.signal,
        }
      )
        .then(res => {
          const data = res?.[params?.fields?.[0]] || [];
          return {
            count: +data?.length || 0,
            list:
              data?.map(item => ({
                id: item,
                name: item,
              })) || [],
          };
        })
        .catch(() => {
          return {
            count: 0,
            list: [],
          };
        });
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
      commonWhere,
      showResidentBtn,
      filterMode,
      checkboxFilters,
      defaultResidentSetting,
      appName,
      fieldMap,
      handleQuery,
      handleAppNameChange,
      handelSceneChange,
      handleFavoriteShowChange,
      handleCloseDimensionPanel,
      handleConditionChange,
      getRetrievalFilterValueData,
      handleCommonWhereChange,
      handleWhereChange,
      handleQueryStringChange,
      handleQueryStringInputChange,
      handleShowResidentBtnChange,
      handleFilterModeChange,
      handleFilterSearch,
      handleCheckboxFiltersChange,
    };
  },
  render() {
    return (
      <div class='trace-explore'>
        <div class='favorite-panel'>
          <FavoriteBox
            type='event'
            onChange={(data: any) => {
              console.log('favorit change', data);
            }}
            onOpenBlank={(data: any) => {
              console.log('favorit open blank', data);
            }}
          />
        </div>
        <div class='main-panel'>
          <div class='header-panel'>
            <TraceExploreHeader
              isShowFavorite={this.isShowFavorite}
              list={this.applicationList}
              onAppNameChange={this.handleAppNameChange}
              onFavoriteShowChange={this.handleFavoriteShowChange}
              onImmediateRefreshChange={this.handleQuery}
              onSceneModeChange={this.handelSceneChange}
              onTimeRangeChange={this.handleQuery}
            />
          </div>
          <div class='trace-explore-content'>
            {this.loading ? (
              <div class='skeleton-element filter-skeleton' />
            ) : (
              <RetrievalFilter
                commonWhere={this.commonWhere}
                dataId={this.appName}
                defaultResidentSetting={this.defaultResidentSetting}
                defaultShowResidentBtn={this.showResidentBtn}
                fields={this.fieldList}
                filterMode={this.filterMode}
                getValueFn={this.getRetrievalFilterValueData}
                queryString={this.queryString}
                residentSettingOnlyId={this.residentSettingOnlyId}
                where={this.where}
                onCommonWhereChange={this.handleCommonWhereChange}
                onModeChange={this.handleFilterModeChange}
                onQueryStringChange={this.handleQueryStringChange}
                onQueryStringInputChange={this.handleQueryStringInputChange}
                onSearch={this.handleFilterSearch}
                onShowResidentBtnChange={this.handleShowResidentBtnChange}
                onWhereChange={this.handleWhereChange}
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
                    <TraceExploreView
                      checkboxFilters={this.checkboxFilters}
                      commonParams={this.commonParams}
                      fieldMap={this.fieldMap}
                      onCheckboxFiltersChange={this.handleCheckboxFiltersChange}
                    />
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
