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
import { useI18n } from 'vue-i18n';
import { useRoute, useRouter } from 'vue-router';

import { useDebounceFn } from '@vueuse/core';
import { listApplicationInfo } from 'monitor-api/modules/apm_meta';
import { listTraceViewConfig } from 'monitor-api/modules/apm_trace';
import { updateFavorite } from 'monitor-api/modules/model';
import { random } from 'monitor-common/utils';
import pinyin from 'tiny-pinyin';

import EmptyStatus from '../../components/empty-status/empty-status';
import RetrievalFilter from '../../components/retrieval-filter/retrieval-filter';
import { EMode, type IWhereItem, type IGetValueFnParams, EMethod } from '../../components/retrieval-filter/typing';
import { useCandidateValue } from '../../components/retrieval-filter/use-candidate-value';
import {
  mergeWhereList,
  SPAN_DEFAULT_RESIDENT_SETTING_KEY,
  TRACE_DEFAULT_RESIDENT_SETTING_KEY,
} from '../../components/retrieval-filter/utils';
import { DEFAULT_TIME_RANGE, handleTransformToTimestamp } from '../../components/time-range/utils';
import { updateTimezone } from '../../i18n/dayjs';
import { useAppStore } from '../../store/modules/app';
import { useTraceExploreStore } from '../../store/modules/explore';
import DimensionFilterPanel from './components/dimension-filter-panel';
import FavoriteBox from './components/favorite-box';
import EditFavorite from './components/favorite-box/components/group-tree/components/render-favorite/components/edit-favorite';
import useGroupList from './components/favorite-box/hooks/use-group-list';
import TraceExploreHeader from './components/trace-explore-header';
import TraceExploreLayout from './components/trace-explore-layout';
import TraceExploreView from './components/trace-explore-view/trace-explore-view';
import { getFilterByCheckboxFilter } from './utils';

import type { ConditionChangeEvent, ExploreFieldList, IApplicationItem, ICommonParams } from './typing';

const TRACE_EXPLORE_SHOW_FAVORITE = 'TRACE_EXPLORE_SHOW_FAVORITE';
updateTimezone(window.timezone);

import './trace-explore.scss';
export default defineComponent({
  name: 'TraceExplore',
  props: {},
  setup() {
    const { t } = useI18n();
    const route = useRoute();
    const router = useRouter();
    const traceExploreLayoutRef = shallowRef<InstanceType<typeof traceExploreLayoutRef>>();
    const store = useTraceExploreStore();
    const appStore = useAppStore();
    const bizId = computed(() => appStore.bizId);
    const { allFavoriteList, run: refreshGroupList } = useGroupList('trace');

    /** 自动查询定时器 */
    let autoQueryTimer = null;
    const applicationLoading = shallowRef(false);
    /** 应用列表 */
    const applicationList = shallowRef<IApplicationItem[]>([]);
    /** 是否展示收藏夹 */
    const isShowFavorite = shallowRef(true);
    /** 视角切换查询 */
    const cacheSceneQuery = new Map<string, Record<string, any>>();

    const filterMode = shallowRef<EMode>(EMode.ui);

    const where = shallowRef<IWhereItem[]>([]);
    /** 常驻筛选 */
    const commonWhere = shallowRef<IWhereItem[]>([]);
    /** 是否展示常驻筛选 */
    const showResidentBtn = shallowRef(false);
    /** 不同视角下维度字段的列表 */
    const fieldListMap = shallowRef<ExploreFieldList>({ trace: [], span: [] });
    /** table上方快捷筛选操作区域（ “包含” 区域中的 复选框组）选中的值 */
    const checkboxFilters = deepRef([]);
    /** 维度字段列表 */
    const fieldList = computed(() => {
      return store.mode === 'trace' ? fieldListMap.value.trace : fieldListMap.value.span;
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
    /** 默认选择的收藏Id */
    const defaultFavoriteId = shallowRef(null);
    /* 当前选择的收藏项 */
    const currentFavorite = shallowRef(null);
    const editFavoriteData = shallowRef(null);
    const editFavoriteShow = shallowRef(false);

    let axiosController = new AbortController();
    const { getFieldsOptionValuesProxy } = useCandidateValue(axiosController);

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

    watch([() => store.timeRange, () => store.refreshImmediate], () => {
      handleQuery();
    });

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
      handleQuery();
    }

    /** 应用切换 */
    async function handleAppNameChange() {
      await getViewConfig();
      handleQuery();
    }

    /** 获取应用列表 */
    async function getApplicationList() {
      applicationLoading.value = true;
      const data = await listApplicationInfo().catch(() => []);
      applicationLoading.value = false;
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
      isShowFavorite.value = JSON.parse(localStorage.getItem(TRACE_EXPLORE_SHOW_FAVORITE) || 'true');
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
        favorite_id,
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
        favorite_id && (defaultFavoriteId.value = Number(favorite_id));
      } catch (error) {
        console.log('route query:', error);
      }
    }

    function setUrlParams() {
      const { favorite_id, ...otherQuery } = route.query;
      const query = {
        ...otherQuery,
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
      // axiosController?.abort?.();
      axiosController = new AbortController();
      const [startTime, endTime] = handleTransformToTimestamp(store.timeRange);
      return getFieldsOptionValuesProxy({
        app_name: store.appName,
        start_time: startTime,
        end_time: endTime,
        fields: params?.fields || [],
        limit: params?.limit || 5,
        filters:
          params?.where?.map(item => ({
            key: item.key,
            operator: 'like',
            value: item.value || [],
          })) || [],
        query_string: params?.queryString || '',
        mode: store.mode,
      } as any)
        .then(res => {
          return {
            count: res.length,
            list: res,
          };
        })
        .catch(() => ({
          count: 0,
          list: [],
        }));
      // return getFieldsOptionValues(
      //   {
      //     app_name: store.appName,
      //     start_time: startTime,
      //     end_time: endTime,
      //     fields: params?.fields || [],
      //     limit: params?.limit || 5,
      //     filters:
      //       params?.where?.map(item => ({
      //         key: item.key,
      //         operator: 'like',
      //         value: item.value || [],
      //       })) || [],
      //     query_string: params?.queryString || '',
      //     mode: store.mode,
      //   },
      //   {
      //     signal: axiosController.signal,
      //   }
      // )
      //   .then(res => {
      //     const data = res?.[params?.fields?.[0]] || [];
      //     return {
      //       count: +data?.length || 0,
      //       list:
      //         data?.map(item => ({
      //           id: item,
      //           name: item,
      //         })) || [],
      //     };
      //   })
      //   .catch(() => {
      //     return {
      //       count: 0,
      //       list: [],
      //     };
      //   });
    }

    /**
     * 处理收藏夹变更的回调函数
     * @param {object} data - 收藏夹配置数据,为空时表示清除收藏
     * @description 当收藏夹变更时:
     * 1. 更新当前收藏夹值
     * 2. 如果有收藏数据,则用收藏的配置更新查询条件(where)、通用查询条件(commonWhere)和查询语句(queryString)
     * 3. 如果清除收藏,则重置所有查询条件为空
     */
    function handleFavoriteChange(data) {
      currentFavorite.value = data || null;
      if (data) {
        const favoriteConfig = data?.config;
        where.value = favoriteConfig?.queryParams?.filters || [];
        commonWhere.value = favoriteConfig?.componentData?.commonWhere || [];
        queryString.value = favoriteConfig?.queryParams?.query || '';
        filterMode.value = favoriteConfig?.componentData?.filterMode || EMode.ui;
        store.init({
          mode: favoriteConfig?.queryParams?.mode || 'trace',
          appName: favoriteConfig?.queryParams?.app_name || store.appName,
          timeRange: favoriteConfig?.componentData?.timeRange || DEFAULT_TIME_RANGE,
          refreshInterval: favoriteConfig?.componentData?.refreshInterval || -1,
        });
      } else {
        where.value = [];
        queryString.value = '';
        commonWhere.value = [];
      }
      handleQuery();
      getViewConfig();
    }

    /** 收藏夹新开标签页 */
    function handleFavoriteOpenBlank(data) {
      const href = `${location.origin}${location.pathname}?bizId=${bizId.value}#${route.path}`;
      window.open(`${href}?favorite_id=${data.id}`, '_blank');
    }

    /**
     * 处理收藏保存的异步函数
     * @param {boolean} isEdit - 是否为编辑模式，默认为 false
     * @description
     * 该函数用于处理 Trace 探索页面的收藏功能：
     * - 收集当前的时间范围、过滤条件等查询参数
     * - 根据 isEdit 参数决定是更新现有收藏还是创建新收藏
     * - 编辑模式下直接更新收藏并刷新列表
     * - 非编辑模式下打开收藏编辑弹窗
     */
    async function handleFavoriteSave(isEdit = false) {
      const [startTime, endTime] = handleTransformToTimestamp(store.timeRange);
      const filters = mergeWhereList(where.value || [], commonWhere.value || []);
      const params = {
        config: {
          componentData: {
            mode: store.mode,
            filterMode: filterMode.value,
            commonWhere: commonWhere.value,
            timeRange: store.timeRange,
            refreshInterval: store.refreshInterval,
          },
          queryParams: {
            app_name: store.appName,
            start_time: startTime,
            end_time: endTime,
            filters: filterMode.value === EMode.queryString ? [] : filters,
            offset: 0,
            limit: 30,
            query: filterMode.value === EMode.queryString ? queryString.value : '',
            sort: [],
            mode: store.mode,
          },
        },
      };
      if (isEdit) {
        await updateFavorite(currentFavorite.value.id, {
          type: 'trace',
          ...params,
        });
        refreshGroupList();
      } else {
        editFavoriteData.value = params;
        editFavoriteShow.value = true;
      }
    }

    function handleEditFavoriteShow(isShow) {
      editFavoriteShow.value = isShow;
    }
    function handleFavoriteShowChange(isShow: boolean) {
      isShowFavorite.value = isShow;
      localStorage.setItem(TRACE_EXPLORE_SHOW_FAVORITE, JSON.stringify(isShow));
    }

    function handleCreateApp() {
      const url = location.href.replace(location.hash, '#/apm/home');
      window.open(url, '_blank');
    }

    return {
      t,
      traceExploreLayoutRef,
      applicationLoading,
      applicationList,
      isShowFavorite,
      fieldListMap,
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
      allFavoriteList,
      defaultFavoriteId,
      currentFavorite,
      editFavoriteShow,
      editFavoriteData,
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
      handleFavoriteChange,
      handleFavoriteOpenBlank,
      handleFavoriteSave,
      handleEditFavoriteShow,
      handleCreateApp,
    };
  },
  render() {
    return (
      <div class='trace-explore'>
        <div
          style={{ display: this.isShowFavorite ? 'block' : 'none' }}
          class='favorite-panel'
        >
          <FavoriteBox
            defaultFavoriteId={this.defaultFavoriteId}
            type='trace'
            onChange={this.handleFavoriteChange}
            onClose={() => this.handleFavoriteShowChange(false)}
            onOpenBlank={this.handleFavoriteOpenBlank}
          />
        </div>
        <div class='main-panel'>
          <div class='header-panel'>
            <TraceExploreHeader
              isShowFavorite={this.isShowFavorite}
              list={this.applicationList}
              onAppNameChange={this.handleAppNameChange}
              onFavoriteShowChange={this.handleFavoriteShowChange}
              onSceneModeChange={this.handelSceneChange}
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
                favoriteList={this.allFavoriteList as any[]}
                fields={this.fieldList as any[]}
                filterMode={this.filterMode}
                getValueFn={this.getRetrievalFilterValueData}
                isShowFavorite={true}
                queryString={this.queryString}
                residentSettingOnlyId={this.residentSettingOnlyId}
                selectFavorite={this.currentFavorite}
                where={this.where}
                onCommonWhereChange={this.handleCommonWhereChange}
                onFavorite={this.handleFavoriteSave}
                onModeChange={this.handleFilterModeChange}
                onQueryStringChange={this.handleQueryStringChange}
                onQueryStringInputChange={this.handleQueryStringInputChange}
                onSearch={this.handleFilterSearch}
                onShowResidentBtnChange={this.handleShowResidentBtnChange}
                onWhereChange={this.handleWhereChange}
              />
            )}
            {!this.applicationLoading && !this.applicationList.length && (
              <div class='create-app-guide'>
                <EmptyStatus
                  textMap={{ 'empty-app': this.t('暂无应用') }}
                  type='empty-app'
                >
                  <p class='subTitle'>
                    <i18n-t keypath='无法查询调用链，请先 {0}'>
                      <span onClick={() => this.handleCreateApp()}>{this.$t('创建应用')}</span>
                    </i18n-t>
                  </p>
                </EmptyStatus>
              </div>
            )}
            {!this.applicationLoading && this.applicationList.length && (
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
                        fieldListMap={this.fieldListMap}
                        onCheckboxFiltersChange={this.handleCheckboxFiltersChange}
                      />
                    </div>
                  ),
                }}
              </TraceExploreLayout>
            )}
          </div>
        </div>
        <EditFavorite
          data={this.editFavoriteData}
          isCreate={true}
          isShow={this.editFavoriteShow}
          onClose={() => this.handleEditFavoriteShow(false)}
          onSuccess={() => this.handleEditFavoriteShow(false)}
        />
      </div>
    );
  },
});
