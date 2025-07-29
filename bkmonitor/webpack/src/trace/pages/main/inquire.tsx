/* eslint-disable vue/multi-word-component-names */
/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition):
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
import {
  computed,
  defineComponent,
  onBeforeUnmount,
  onDeactivated,
  onMounted,
  onUnmounted,
  provide,
  reactive,
  ref,
  shallowRef,
} from 'vue';

// import TemporaryShare from '../../components/temporary-share/temporary-share';
import * as authorityMap from 'apm/pages/home/authority-map';
import axios from 'axios';
import { Button, Cascader, Dialog, Input, Popover, Radio } from 'bkui-vue';
import { listApplicationInfo } from 'monitor-api/modules/apm_meta';
import {
  getFieldOptionValues,
  listServiceStatistics,
  listSpan,
  listSpanStatistics,
  listStandardFilterFields,
  listTrace,
  spanDetail,
  traceDetail,
  traceOptions,
} from 'monitor-api/modules/apm_trace';
import { createQueryHistory, destroyQueryHistory, listQueryHistory } from 'monitor-api/modules/model';
import { skipToDocsLink } from 'monitor-common/utils/docs';
import { deepClone, random } from 'monitor-common/utils/utils';
import { debounce } from 'throttle-debounce';
import { useI18n } from 'vue-i18n';
import { useRoute, useRouter } from 'vue-router';

import Condition from '../../components/condition/condition';
import DeleteDialogContent from '../../components/delete-dialog-content/delete-dialog-content';
import { type TimeRangeType, DEFAULT_TIME_RANGE, handleTransformToTimestamp } from '../../components/time-range/utils';
import transformTraceTree from '../../components/trace-view/model/transform-trace-data';
import VerifyInput from '../../components/verify-input/verify-input';
import { destroyTimezone, getDefaultTimezone, updateTimezone } from '../../i18n/dayjs';
import {
  REFRESH_IMMEDIATE_KEY,
  REFRESH_INTERVAL_KEY,
  TIME_OFFSET_KEY,
  TIME_RANGE_KEY,
  TIMEZONE_KEY,
  useIsEnabledProfilingProvider,
  VIEW_OPTIONS_KEY,
} from '../../plugins/hooks';
import { DEFAULT_TRACE_DATA, QUERY_TRACE_RELATION_APP } from '../../store/constant';
import { useSearchStore } from '../../store/modules/search';
import { type IServiceStatisticsType, type ListType, useTraceStore } from '../../store/modules/trace';
import { monitorDrag } from '../../utils/drag-directive';
import DurationFilter from './duration-filter/duration-filter';
import HandleBtn from './handle-btn/handle-btn';
import InquireContent from './inquire-content';
import SearchHeader from './search-header/search-header';
import SearchLeft, { formItem } from './search-left/search-left';

import type { ISelectMenuOption } from '../../components/select-menu/select-menu';
import type { Span } from '../../components/trace-view/typings';
import type { IViewOptions } from '../../plugins/typings';
import type {
  IAppItem,
  IFavoriteItem,
  IScopeSelect,
  // ISearchSelectItem,
  ISearchSelectValue,
  ITraceData,
  SearchType,
} from '../../typings';
import type { IEventRetrieval, IFilterCondition } from 'monitor-pc/pages/data-retrieval/typings';

import './inquire.scss';

interface IState {
  app: string;
  autoQuery: boolean;
  cacheQueryAppName: string;
  isAlreadyAccurateQuery: boolean;
  isAlreadyScopeQuery: boolean;
  leftWidth: number;
  searchType: SearchType;
  showLeft: boolean;
}

interface Params {
  app_name: string;
  bk_biz_id: number | string;
  query_trace_relation_app?: boolean;
  span_id?: number | string;
  trace_id?: number | string;
}

/** 头部工具栏高度 */
const HEADER_HEIGHT = 48;
export default defineComponent({
  name: 'Inquire',
  directives: { monitorDrag },
  setup(props, { expose }) {
    const route = useRoute();
    const router = useRouter();
    const store = useTraceStore();
    const { t } = useI18n();
    const selectedListType = computed(() => store.listType);
    // TODO：后续补上类型
    const tempSortList: any[] = [];
    const sortList: any[] = [];
    const leftDefaultWidth = document.body.clientWidth > 1440 ? 400 : 320;
    const state = reactive<IState>({
      app: '',
      showLeft: true,
      autoQuery: true,
      leftWidth: 400,
      searchType: 'accurate',
      /** 是否已经查询过 初始显示占位 */
      isAlreadyAccurateQuery: false,
      isAlreadyScopeQuery: false,
      /** 最近一次检索的应用 */
      cacheQueryAppName: (route.query.app_name as string) || localStorage.getItem('trace_query_app') || '',
    });
    // 自定义筛选列表
    const conditionFilter = [];
    // 自定义筛选组件信息列表
    const conditionList = reactive([]);
    // 应用列表
    const appList = shallowRef<IAppItem[]>([]);
    const searchStore = useSearchStore();
    /** 获取应用列表 */
    const getAppList = async () => {
      const listData = await listApplicationInfo().catch(() => []);
      appList.value = listData;
      isEmptyApp.value = !listData.length;

      setTimeout(async () => {
        // 初始赋值自定义回显内容 组件需做优化处理 暂时使用 setTimeout 定时器
        if (appList.value.length && state.app === '') {
          if (
            state.cacheQueryAppName &&
            appList.value.find(
              app => app.app_name === state.cacheQueryAppName && app.permission[authorityMap.VIEW_AUTH]
            )
          ) {
            state.app = state.cacheQueryAppName;
          } else {
            const defaultApp = appList.value.find(app => app.permission?.[authorityMap.VIEW_AUTH])?.app_name;
            state.app = defaultApp || '';
          }
          handleAppSelectChange(state.app);
        }
      }, 100);
    };
    getAppList();
    const timeRange = ref<TimeRangeType>(DEFAULT_TIME_RANGE);
    const cacheTimeRange = ref('');
    const enableSelectionRestoreAll = ref(true);
    const showRestore = ref(false);
    let cancelTokenSource = null;
    const timezone = ref<string>(getDefaultTimezone());
    const refreshImmediate = ref<number | string>('');
    /* 此时间下拉加载时不变 */
    const curTimestamp = ref<number[]>(handleTransformToTimestamp(timeRange.value));
    const refreshInterval = ref<number>(-1);
    const refreshIntervalInstance = ref<any>(null);
    const defaultViewOptions = ref<IViewOptions>({});
    /** 查询语句提示文本 */
    const tipsContentList: IEventRetrieval.ITipsContentListItem[] = [
      { label: t('精确匹配(支持AND、OR)：'), value: ['author:"John Smith" AND age:20'] },
      { label: t('字段名匹配(*代表通配符):'), value: ['status:active', 'title:(quick brown)'] },
      { label: t('字段名模糊匹配:'), value: ['vers\\*on:(quick brown)'] },
      { label: t('通配符匹配:'), value: ['qu?ck bro*'] },
      { label: t('正则匹配:'), value: ['name:/joh?n(ath[oa]n/'] },
      { label: t('范围匹配:'), value: ['count:[1 TO 5]', 'count:[1 TO 5}', 'count:[10 TO *]'] },
    ];
    const headerToolMenuList: ISelectMenuOption[] = [{ id: 'config', name: t('应用设置') }];

    function handleChartDataZoom(value) {
      if (JSON.stringify(timeRange.value) !== JSON.stringify(value)) {
        cacheTimeRange.value = JSON.parse(JSON.stringify(timeRange.value));
        timeRange.value = value;
        showRestore.value = true;
      }
    }
    function handleRestoreEvent() {
      timeRange.value = JSON.parse(JSON.stringify(cacheTimeRange.value));
      showRestore.value = false;
    }
    // 框选图表事件范围触发（触发后缓存之前的时间，且展示复位按钮）
    provide('showRestore', showRestore);
    provide('enableSelectionRestoreAll', enableSelectionRestoreAll);
    provide('handleChartDataZoom', handleChartDataZoom);
    provide('handleRestoreEvent', handleRestoreEvent);
    provide(TIME_RANGE_KEY, timeRange);
    provide(TIMEZONE_KEY, timezone);
    provide(REFRESH_INTERVAL_KEY, refreshInterval);
    provide(REFRESH_IMMEDIATE_KEY, refreshImmediate);
    provide(VIEW_OPTIONS_KEY, defaultViewOptions);
    provide(TIME_OFFSET_KEY, ref([]));
    const autoQueryPopover = ref(null);
    const searchIdType = ref('traceID');
    const searchResultIdType = ref('traceID'); // 用于传递到搜索结果组件 由于切换精确查询 ID 方式 当未搜索时会清空输入内容 但需要保证右侧原有搜索结果不变
    const traceIDSearchValue = ref<string>('');
    const traceIdInput = ref<HTMLDivElement>();
    /* 范围查询动态表单 */
    const scopeSelects = ref<{ [id: string]: IScopeSelect }>({});
    /* 查询语句 */
    const queryString = ref('');
    /* trace_list 分页 */
    const traceListPagination = reactive({
      offset: 0,
      limit: 30,
    });
    /* trace_list 下拉加载loading */
    const traceListTableLoading = ref(false);
    /* trace kind(tracelist 筛选) */
    const traceKind = ref('all');
    /** 排序字段 */
    const traceSortKey = ref('');
    // 收藏列表
    const collectList = shallowRef<IFavoriteItem[]>([]);
    getCollectList();
    /* collect dialog */
    const collectDialog = reactive({
      show: false,
      loading: false,
      name: '',
      id: 0,
    });
    const isEmptyApp = ref<boolean>(false);
    // const searchSelectData = shallowRef<ISearchSelectItem[]>([]);
    const searchSelectValue = ref<ISearchSelectValue[]>([]);
    const durationRange = ref<null | number[]>(null);
    const traceColumnFilters = ref<Record<string, string[]>>({});
    const cacheTraceColumnFilters = ref<Record<string, string[]>>({});
    const interfaceListCanLoadMore = ref<boolean>(false);
    const serviceListCanLoadMore = ref<boolean>(false);
    const spanDetails = ref<null | Span>(null);

    const isLoading = computed<boolean>(() => store.loading);
    const isPreCalculationMode = computed(() => store.traceListMode === 'pre_calculation');
    const collectCheckValue = ref(queryScopeParams());

    const enableProfiling = computed(
      () => !!appList.value.find(item => item.app_name === state.app)?.is_enabled_profiling
    );

    const traceViewFilters = computed(() => store.traceViewFilters);

    const setSelectedTypeByRoute = () => {
      const listType = (route.query.listType as ListType) || 'trace';
      const selectedType = JSON.parse((route.query.selectedType as string) || '[]');
      const selectedInterfaceType = JSON.parse((route.query.selectedInterfaceType as string) || '[]');
      switch (listType) {
        case 'trace':
          if (selectedType.length) store.setTraceType(selectedType);
          break;
        case 'span':
          if (selectedType.length) store.setSpanType(selectedType);
          break;
        case 'interfaceStatistics':
          if (selectedType.length) store.setInterfaceStatisticsType(selectedType);
          break;
        case 'serviceStatistics':
          if (selectedType.length || selectedInterfaceType.length)
            store.setServiceStatisticsType({
              contain: selectedType,
              interfaceType: selectedInterfaceType,
            });
          break;
      }
    };
    setSelectedTypeByRoute();

    useIsEnabledProfilingProvider(enableProfiling);

    const handleLeftHiddenAndShow = (val: boolean) => {
      state.showLeft = val;
    };

    const handleChangeQuery = (val: SearchType) => {
      state.searchType = val;
      val === 'accurate' && traceIdInput.value?.focus?.();
      if (state.autoQuery && state.searchType === 'scope') {
        handleQueryScopeDebounce();
        getStandardFields();
      }
    };

    /**
     * @description: 切换自动查询开关
     * @param {boolean} val
     */
    const handleAutoQueryChange = (val: boolean) => {
      localStorage.setItem('bk_monitor_auto_query_enable', `${val}`);
      state.autoQuery = val;
    };
    async function handleAppSelectChange(val: string, isClickQueryBtn = false) {
      state.app = val;
      traceListPagination.offset = 0;
      traceColumnFilters.value = {};
      if (val) {
        if (!Object.keys(scopeSelects.value).length) {
          await getQueryOptions();
        }
        // 获取图表配置列表
        searchStore.getPanelList(state.app);
        if (state.searchType === 'scope' && (state.autoQuery || !state.isAlreadyScopeQuery || isClickQueryBtn)) {
          if (state.isAlreadyScopeQuery) reGetFieldOptionValues();
          handleQueryScopeDebounce(true);
        }
      }
    }
    /** 获取范围查询条件 */
    const getQueryOptions = async () => {
      const options = await traceOptions().catch(() => []);
      scopeSelects.value = {};
      options.forEach((item: IScopeSelect) => {
        scopeSelects.value[item.id] = { ...item, key: random(8), value: [] };
      });
    };
    /** 切换ID精确查询类型 */
    const handleChangeSearchIdType = () => {
      traceIDSearchValue.value = '';
    };
    /** ID 查询 */
    const handleQueryTraceId = async () => {
      if (!state.app || isLoading.value || !traceIDSearchValue.value.trim?.().length) {
        return;
      }

      router.replace({
        name: route.name || 'home',
        query: {
          app_name: state.app,
          search_type: state.searchType,
          search_id: searchIdType.value,
          trace_id: traceIDSearchValue.value,
        },
      });
      store.setPageLoading(true);
      /** 记录当前搜索的应用 */
      localStorage.setItem('trace_query_app', state.app);

      const isTraceIDSearch = searchIdType.value === 'traceID';
      const requestFn = isTraceIDSearch ? traceDetail : spanDetail;
      const params: Params = {
        bk_biz_id: window.bk_biz_id,
        app_name: state.app,
        [isTraceIDSearch ? 'trace_id' : 'span_id']: traceIDSearchValue.value,
      };
      if (isTraceIDSearch && (!store.selectedTraceViewFilterTab || store.selectedTraceViewFilterTab === 'timeline')) {
        params[QUERY_TRACE_RELATION_APP] = traceViewFilters.value.includes(QUERY_TRACE_RELATION_APP);
      }
      const resultData = await requestFn(params).catch(() => null);
      searchResultIdType.value = searchIdType.value;
      if (isTraceIDSearch) {
        store.setTraceData({ ...resultData, appName: state.app, trace_id: traceIDSearchValue.value });
      } else {
        if (resultData && Object.keys(resultData).length) {
          store.setSpanDetailData(resultData);
          resultData.trace_tree.traceID = resultData?.trace_tree?.spans?.[0]?.traceID;
          spanDetails.value = transformTraceTree(resultData.trace_tree)?.spans?.[0];
        } else {
          spanDetails.value = null;
        }
      }
      store.setPageLoading(false);
      if (!state.isAlreadyAccurateQuery) {
        state.isAlreadyAccurateQuery = true;
      }
    };
    /** 精确查询输入框失焦 */
    const handleQueryIDInputBlur = () => {
      if (traceIDSearchValue.value.trim?.().length && state.autoQuery) {
        handleQueryTraceId();
      }
    };
    /* 范围查询参数 */
    function queryScopeParams() {
      type IFilterItem = {
        key: string;
        operator: 'between' | 'equal' | 'logic' | 'not_equal';
        value: Array<any>;
      };
      let filters: IFilterItem[] = [];

      // 收集 Trace 列表 表头的查询信息
      Object.keys(traceColumnFilters.value || {}).forEach(key => {
        // 特殊处理trace视角表头状态码在非标准字段查询模式下的key和operator值
        const isOriginStatusCodeFilter = key === 'root_service_status_code' && !isPreCalculationMode.value;
        filters.push({
          key: isOriginStatusCodeFilter ? 'status_code' : key,
          operator: isOriginStatusCodeFilter ? 'logic' : 'equal',
          value: traceColumnFilters.value?.[key],
        });
      });
      let cacheFilter = cacheTraceColumnFilters.value[selectedListType.value] || [];
      // 收集 耗时 区间信息
      if (durationRange?.value) {
        filters.push({
          key: 'duration',
          value: durationRange?.value,
          operator: 'between',
        });
      } else {
        cacheFilter = cacheFilter.filter(item => item.key !== 'duration');
      }

      const updatedCacheFilter = filters.reduce((acc, item) => {
        const index = acc.findIndex(filter => filter.key === item.key);
        if (index !== -1) {
          acc[index].value = item.value;
        } else {
          acc.push(item);
        }
        return acc;
      }, cacheFilter);
      // 过滤出有值的项
      const filterData = updatedCacheFilter.filter(ele => (ele.value || []).length > 0);
      // 更新缓存和 filters
      cacheTraceColumnFilters.value[selectedListType.value] = updatedCacheFilter;
      filters = filterData;

      // 收集 侧边栏：服务
      Object.keys(scopeSelects.value).forEach(key => {
        if (key === 'service' && scopeSelects.value[key].value.length) {
          filters.push({
            key: scopeSelects.value[key].trace_key,
            value: scopeSelects.value[key].value,
            operator: 'equal',
          });
        }
      });
      // 收集 侧边栏：条件查询
      searchSelectValue?.value?.forEach(item => {
        // 这里不会将 or 、and 逻辑操作符带入到 filters 里。
        if (item.values) {
          filters.push({
            key: scopeSelects.value[item.id].trace_key,
            value: item.values.map(value => value.id),
            operator: 'equal',
          });
        }
      });
      if (conditionFilter.length) {
        conditionFilter.forEach(item => {
          if (item.value.length) filters.push(item);
        });
      } else {
        const { conditionList: conditionListStringify } = route.query;
        if (conditionListStringify) {
          const result = JSON.parse(conditionListStringify as string);
          for (const key in result) {
            if (result[key]?.selectedConditionValue?.length) {
              filters.push({
                key,
                operator: result[key].selectedCondition.value,
                value: result[key].selectedConditionValue,
              });
            }
          }
        }
      }

      if (selectedListType.value === 'trace') {
        const filterTypeMapping = {
          error: {
            key: 'error',
            operator: 'logic',
            value: [],
          },
        };
        store.traceType.forEach(item => filters.push(filterTypeMapping[item]));
      }
      // TODO：后面回来还需要收集侧边栏的信息
      // 收集 Span 视角 里的 SpanType 对应的固定过滤。
      if (selectedListType.value === 'span') {
        const filterMapSpanType = {
          root_span: { key: 'parent_span_id', operator: 'equal', value: [''] },
          entry_span: { key: 'kind', operator: 'equal', value: ['2', '5'] },
          error: { key: 'status.code', operator: 'equal', value: ['2'] },
        };
        const result = store.spanType.map(item => filterMapSpanType[item]);
        filters.push(...result);
      }
      if (selectedListType.value === 'interfaceStatistics') {
        // 将 store.interfaceStatisticsType string 数组凑成一个 filter 具体的转换表要等后端出来
        const filterMapSpanType = {
          root_span: { key: 'root_span', operator: 'logic', value: [] },
          root_service_span: { key: 'root_service_span', operator: 'logic', value: [] },
          'status.code': { key: 'status.code', operator: 'equal', value: ['2'] },
        };
        const result = store.interfaceStatisticsType.map(item => filterMapSpanType[item]);
        filters.push(...result);

        // 在这里将以下三个 string 数组凑成一个 filter 具体的转换表要等后端出来
        // store.interfaceStatisticsType.selectedInterfaceStatisticsType
        // store.interfaceStatisticsType.selectedInterfaceTypeInInterfaceStatistics
        // store.interfaceStatisticsType.selectedSourceTypeInInterfaceStatistics
      }
      if (selectedListType.value === 'serviceStatistics') {
        const filterTypeMapping = {
          error: {
            key: 'status.code',
            operator: 'equal',
            value: ['2'],
          },
          sync: {
            key: 'kind',
            operator: 'equal',
            value: ['2', '3'],
          },
          async: {
            key: 'kind',
            operator: 'equal',
            value: ['4', '5'],
          },
          internal: {
            key: 'kind',
            operator: 'equal',
            value: ['1'],
          },
          unknown: {
            key: 'kind',
            operator: 'equal',
            value: ['0'],
          },
        };
        store.serviceStatisticsType.contain.forEach(item => filters.push(filterTypeMapping[item]));
        store.serviceStatisticsType.interfaceType.forEach(item => filters.push(filterTypeMapping[item]));
      }
      const params = {
        app_name: state.app,
        // 改 key
        // query_string: queryString.value,
        query: queryString.value,
        start_time: curTimestamp.value[0],
        end_time: curTimestamp.value[1],
        // 去掉
        // trace_kind: traceKind.value,
        offset: traceListPagination.offset,
        limit: traceListPagination.limit,
        // 改 key
        // filter_dict: filters,
        filters,
        // 改为传数组
        // sort: traceSortKey.value,
        sort: sortList,
        // 去掉，统一合并到 filter 上。
        duration: durationRange?.value ?? undefined,
        // 合并到 filters
        // trace_filter: traceColumnFilters?.value
      };
      // 特殊处理 Trace list 的排序
      if (selectedListType.value === 'trace') {
        params.sort = [...sortList];
      }
      // 由于服务端接口还未完善，这里先特殊处理。sortList 只能传一个，且 sortList 最后一项是最后一次选择的排序。
      // 这里只传最后一个项。后端接口能完全支持多个筛选，就把以下判断代码删掉即可
      if (params.sort.length > 1) {
        params.sort = [params.sort[params.sort.length - 1]];
      }
      return params;
    }
    /* 范围查询 */
    async function handleQueryScope(isClickQueryBtn = false, needLoading = true) {
      if ((!state.autoQuery && !isClickQueryBtn && state.isAlreadyScopeQuery) || !state.app) {
        return;
      }
      if (needLoading) {
        store.setPageLoading(true);
        store.setTraceDetail(false);
        store.setFilterTraceList([]);
      }
      const params = queryScopeParams();
      // 查询语句 的字段检查，非标准要换成 span 视角
      // if (selectedListType.value === 'trace') {
      //   // 克隆防止影响后续的正常请求。
      //   const clonedFilter = deepClone(params.filters);
      //   // 把 耗时 项去掉。
      //   const filters = clonedFilter.filter(item => item.key !== 'duration');
      //   const queryStringCheckResult = await isContainNonStandardField({
      //     query: queryString.value,
      //     filters
      //   }).catch(() => []);
      //   if (!queryStringCheckResult) {
      //     // 切换到 span 视角选项，后面会正常请求。
      //     store.setListType('span');
      //   }
      // }

      setRouterQueryParams(params);
      collectCheckValue.value = params;
      // Trace List 查询相关
      if (selectedListType.value === 'trace') {
        store.setTraceLoading(true);
        try {
          const listData = await listTrace(params, { cancelToken: cancelTokenSource?.token }).catch(() => []);
          const { total, data, type = 'pre_calculation' } = listData;
          store.setTraceListMode(type);
          store.setTraceTotalCount(total);
          if (traceListPagination.offset > 1) {
            // 两个区间可能会包含同一个trace的span 这里需要去重
            const list = [...store.traceList];
            data.forEach((trace: ITraceData) => {
              if (list.every(val => val.trace_id !== trace.trace_id)) {
                list.push(trace);
              }
            });
            store.setTraceList(list);
          } else {
            store.setTraceList(data);
          }
        } catch {
        } finally {
          store.setTraceLoading(false);
        }
      }
      // Span List 查询相关
      if (selectedListType.value === 'span') {
        store.setTraceLoading(true);
        try {
          const spanListData = await listSpan(params).catch(() => []);
          const { total, data } = spanListData;
          store.setTraceTotalCount(total);

          if (traceListPagination.offset > 1) {
            // TODO：这里可能会有重复的 span ID ，需要去重。
            store.setSpanList(store.spanList.concat(data));
          } else {
            store.setSpanList(data);
          }
        } catch {
        } finally {
          store.setTraceLoading(false);
        }
      }
      // 接口统计 查询相关
      if (selectedListType.value === 'interfaceStatistics') {
        store.setTraceLoading(true);
        try {
          interfaceListCanLoadMore.value = true;
          // 请求接口
          // store 设置相关 list
          const interfaceStatisticsList = await listSpanStatistics(params).catch(() => []);
          if (interfaceStatisticsList.length < traceListPagination.limit) {
            // 当前页返回不足一页数量则说明请求完所有数据
            interfaceListCanLoadMore.value = false;
          }
          if (traceListPagination.offset > 1) {
            store.setInterfaceStatisticsList(store.interfaceStatisticsList.concat(interfaceStatisticsList));
          } else {
            store.setInterfaceStatisticsList(interfaceStatisticsList);
          }
          // store.setTraceTotalCount(store.interfaceStatisticsList.length);
        } catch {
        } finally {
          store.setTraceLoading(false);
        }
      }
      // 服务统计 查询相关
      if (selectedListType.value === 'serviceStatistics') {
        store.setTraceLoading(true);
        try {
          serviceListCanLoadMore.value = true;
          const serviceStatisticList = await listServiceStatistics(params).catch(() => []);
          if (serviceStatisticList.length < traceListPagination.limit) {
            // 当前页返回不足一页数量则说明请求完所有数据
            serviceListCanLoadMore.value = false;
          }
          if (traceListPagination.offset > 1) {
            store.setServiceStatisticsList(store.serviceStatisticsList.concat(serviceStatisticList));
          } else {
            store.setServiceStatisticsList(serviceStatisticList);
          }
        } catch {
        } finally {
          store.setTraceLoading(false);
        }
      }

      if (needLoading) {
        store.setPageLoading(false);
      }
      if (!state.isAlreadyScopeQuery) {
        state.isAlreadyScopeQuery = true;
      }
    }
    const setRouterQueryParams = (paramsValue?) => {
      const params = paramsValue || queryScopeParams();
      const filters: any = {};
      const query: any = {
        app_name: params.app_name,
        search_type: state.searchType,
        search_id: searchIdType.value,
        start_time: timeRange.value[0],
        end_time: timeRange.value[1],
        refreshInterval: refreshInterval.value,
      };
      // 来自故障根因跳转到span中需要额外使用的参数
      if (route.query?.incident_query) {
        try {
          query.incident_query = route.query?.incident_query;
        } catch {}
      }
      Object.keys(scopeSelects.value).forEach(key => {
        if (key === 'service') {
          if (scopeSelects.value[key].value.length) {
            filters[scopeSelects.value[key].id] = scopeSelects.value[key].value;
          }
        } else if (searchSelectValue.value.length) {
          searchSelectValue.value.forEach(opt => (filters[opt.id] = opt.values.map(val => val.id)));
        }
      });

      if (Object.keys(filters).length) {
        query.filters = JSON.stringify(filters);
      }

      if (params.query?.length) {
        query.query = params.query;
      }

      if (params.duration) {
        query.duration = params.duration;
      }

      query.listType = store.listType;

      if (conditionList.length) {
        // 不需要把整个 conditionList 都持久化（数据太多），只保留选中的各种值
        const filterConditionList = {};
        conditionList.forEach(item => {
          if (item.isInclude && item.selectedConditionValue.length) {
            filterConditionList[item.labelValue] = {
              selectedCondition: item.selectedCondition,
              isInclude: item.isInclude,
              selectedConditionValue: item.selectedConditionValue,
            };
          }
        });
        // vue-router 不支持直接把对象转为 query，这里用序列化转一次。
        if (Object.keys(filterConditionList).length) query.conditionList = JSON.stringify(filterConditionList);
      }

      let selectedType = [];
      let selectedInterfaceType = [];
      switch (store.listType) {
        case 'trace':
          selectedType = JSON.stringify(store.traceType) as unknown as string[];
          if (store.traceType.length) query.selectedType = selectedType;
          break;
        case 'span':
          selectedType = JSON.stringify(store.spanType) as unknown as string[];
          if (store.spanType.length) query.selectedType = selectedType;
          break;
        case 'interfaceStatistics':
          selectedType = JSON.stringify(store.interfaceStatisticsType) as unknown as string[];
          if (store.interfaceStatisticsType.length) query.selectedType = selectedType;
          break;
        case 'serviceStatistics':
          selectedType = JSON.stringify(store.serviceStatisticsType.contain) as unknown as string[];
          selectedInterfaceType = JSON.stringify(store.serviceStatisticsType.interfaceType) as unknown as string[];
          if (store.serviceStatisticsType.contain.length) query.selectedType = selectedType;
          if (store.serviceStatisticsType.interfaceType.length) query.selectedInterfaceType = selectedInterfaceType;
          break;
      }

      router.replace({
        name: route.name || 'home',
        query,
      });
    };
    const handleQueryScopeDebounce = debounce(300, handleQueryScope);
    /* 范围查询动态参数更新 */
    function handleScopeQueryChange(isClickQueryBtn = false) {
      traceListPagination.offset = 0;
      curTimestamp.value = handleTransformToTimestamp(timeRange.value);
      handleQueryScopeDebounce(isClickQueryBtn);
    }
    /** 更新耗时过滤条件 */
    function handleDurationChange(range: number[]) {
      durationRange.value = range;
      handleScopeQueryChange();
    }
    /* 切换查询方式 */
    async function handleSearchTypeChange(id: string) {
      store.setTraceDetail(false);
      cancelTokenSource?.cancel?.();
      cancelTokenSource = axios.CancelToken.source();
      if (id === 'scope') {
        if (!state.isAlreadyScopeQuery) {
          state.isAlreadyScopeQuery = true;
        }
        traceKind.value = 'all';
        handleScopeQueryChange(true);
        // 点击 范围查询 在这里做一些准备请求
        // 以免出现重复默认项
        conditionList.length = 0;
        getStandardFields();
      } else {
        if (traceIDSearchValue.value) {
          handleQueryTraceId();
        } else {
          setTimeout(() => {
            traceIdInput.value?.focus?.();
          }, 10);
          store.setTraceData({ ...DEFAULT_TRACE_DATA, appName: state.app });
        }
      }
    }
    /* 收藏  */

    async function handleAddCollect({
      value,
      hideCallback,
      favLoadingCallBack,
    }: {
      favLoadingCallBack: (show: boolean) => void;
      hideCallback: () => void;
      value: string;
    }) {
      // 条件查询值映射
      searchSelectValue.value.forEach(item => {
        if (scopeSelects.value[item.id]) {
          scopeSelects.value[item.id].value = item.values.map(val => val.id);
        }
      });
      const params = {
        type: 'trace',
        name: value,
        config: {
          queryParams: queryScopeParams(),
          componentData: {
            scopeSelects: scopeSelects.value,
            queryString: queryString.value,
            app: state.app,
          },
        },
      };
      favLoadingCallBack(true);
      await createQueryHistory(params)
        .then(() => {
          hideCallback();
          getCollectList();
        })
        .catch(() => false)
        .finally(() => favLoadingCallBack(false));
    }
    /* 选中收藏item */
    function handleSelectCollect(id: number) {
      state.searchType = 'scope';
      const collectItem = collectList.value.find(item => String(item.id) === String(id));
      const { componentData, queryParams } = collectItem.config;
      state.app = componentData?.app || queryParams?.app_name || '';
      if (componentData.scopeSelects) {
        for (const key in componentData.scopeSelects) {
          if (scopeSelects.value[key]) {
            scopeSelects.value[key].value = componentData.scopeSelects[key].value;
            scopeSelects.value[key].key = random(8);
          }
        }
      } else {
        for (const item of queryParams?.filters || []) {
          if (scopeSelects.value[item.key]) {
            scopeSelects.value[item.key].value = item.value;
            scopeSelects.value[item.key].key = random(8);
          }
        }
      }

      // 条件查询值映射
      const historySearchSelectValue: any[] = [];
      for (const key in scopeSelects.value) {
        const values = scopeSelects.value[key].value;
        if (values.length) {
          const curOptions = standardFieldList.value.find(item => item.id === key);
          if (curOptions) {
            let optionValue = curOptions.children.filter(val => values.includes(val.id));
            if (!optionValue.length) {
              // 条件值不存在可选列表
              optionValue = values.map(val => ({ id: val, name: val }));
            }
            historySearchSelectValue.push({
              id: key,
              name: curOptions.name,
              values: optionValue,
            });
          }
        }
      }
      searchSelectValue.value.splice(0, searchSelectValue.value.length, ...historySearchSelectValue);
      queryString.value = componentData.queryString;
      traceListPagination.offset = 0;
      curTimestamp.value = handleTransformToTimestamp(timeRange.value);
      // 获取图表配置列表
      searchStore.getPanelList(state.app);
      handleQueryScope();
    }
    /* 收藏列表 */
    async function getCollectList() {
      collectList.value = await listQueryHistory({
        type: 'trace',
      }).catch(() => []);
    }
    /* 点击查询 */
    function handleClickQuery() {
      handleSelectComplete();
      traceListPagination.offset = 0;
      curTimestamp.value = handleTransformToTimestamp(timeRange.value);
      handleQueryScopeDebounce(true);
      refreshImmediate.value = random(10);
    }
    // 表头排序收集
    function handleTraceListColumnSort(value: any) {
      // tempSortList 会一直保存排序配置，重复点击排序会出现重复项，这里先排除重复项。
      const targetIndex = tempSortList.findIndex(item => item.column.field === value.column.field);
      if (targetIndex >= 0) tempSortList.splice(targetIndex, 1);
      tempSortList.push(value);
      sortList.length = 0;
      tempSortList.forEach(item => {
        if (item.type === 'desc') {
          sortList.push(`-${item.column.field}`);
        } else if (item.type === 'asc') {
          sortList.push(`${item.column.field}`);
        }
      });
      handleScopeQueryChange();
    }
    /* 清空 */
    function handleClearQuery() {
      queryString.value = '';
      Object.keys(scopeSelects.value).forEach(key => {
        scopeSelects.value[key] = { ...scopeSelects.value[key], value: [], key: random(8) };
      });
      searchSelectValue.value = [];
      durationRange.value = null;
      // 清空条件列表
      conditionList.forEach(item => {
        item.selectedConditionValue.length = 0;
      });
      handleScopeQueryChange();
    }
    /* 删除收藏 */
    function handleDeleteCollect(id: number) {
      const name = collectList.value.find(item => item.id === id)?.name as string;
      collectDialog.id = id;
      collectDialog.name = name || '';
      collectDialog.show = true;
    }
    async function deleteCollect() {
      collectDialog.loading = true;
      await destroyQueryHistory(collectDialog.id, { type: 'trace' }).catch(() => false);
      await getCollectList();
      collectDialog.loading = false;
      collectDialog.show = false;
    }
    /* 列表滚动加载 */
    async function handleTraceListScrollBottom() {
      let len = 0;
      if (store.listType === 'trace') {
        len = store.traceList.length + traceListPagination.limit;
      } else if (store.listType === 'span') {
        len = store.spanList.length + traceListPagination.limit;
      } else if (store.listType === 'interfaceStatistics') {
        len = store.interfaceStatisticsList.length;
      } else if (store.listType === 'serviceStatistics') {
        len = store.serviceStatisticsList.length;
      }
      // const len = store.listType === 'trace' ? store.traceList.length : store.spanList.length;

      if (['trace', 'span'].includes(store.listType) && store.totalCount === len) return;

      // 接口统计、服务统计 列表比较特殊，是否到最后一页需要自己去判断。
      if (store.listType === 'interfaceStatistics' && !interfaceListCanLoadMore.value) return;
      if (store.listType === 'serviceStatistics' && !serviceListCanLoadMore.value) return;
      traceListTableLoading.value = true;
      traceListPagination.offset = len;
      await handleQueryScope(true, false);
      traceListTableLoading.value = false;
    }
    function handleAddCondition(val: IFilterCondition.localValue) {
      let temp = '';
      val.value.forEach((item, index) => {
        if (index === 0 && !queryString.value && val.method === 'AND') {
          temp += `${val.key}: "${item}" `;
        } else if (queryString.value && val.method === 'NOT') {
          temp += `AND ${val.method} ${val.key}: "${item}" `;
        } else {
          temp += `${val.method} ${val.key}: "${item}" `;
        }
      });
      queryString.value += temp;
      handleScopeQueryChange();
    }
    /* 时间切换 */
    function handleTimeRangeChange(value: TimeRangeType) {
      timeRange.value = value;
      handleScopeQueryChange();
    }
    function handleTimezoneChange(v: string) {
      timezone.value = v;
      window.timezone = v;
      updateTimezone(v);
      handleScopeQueryChange();
    }

    // 重新获取侧边栏的 条件候选值 ，并将之前所选中的值重置（因为不同时间段的候选值都不一样）。
    async function reGetFieldOptionValues() {
      const time = handleTransformToTimestamp(timeRange.value);
      const fields = conditionList.map(item => item.labelValue);
      const params = {
        app_name: state.app,
        start_time: time[0],
        end_time: time[1],
        bk_biz_id: window.bk_biz_id,
        fields,
      };
      if (!fields.length) return;
      // 在查询前，把 候选项 和 选中项 先清空
      conditionList.forEach((item: any) => {
        item.conditionValueList.length = 0;

        item.selectedConditionValue.length = 0;
      });
      // 无应用时不调用getFieldOptionValues API
      if (!params.app_name) return;
      const result = await getFieldOptionValues(params)
        .catch(() => {})
        .finally(() => (isAddConditionButtonLoading.value = false));
      // 请求成功后，将 候选项 补上。
      conditionList.forEach((item: any) => {
        item.conditionValueList = result[item.labelValue];
      });
    }
    /* 列表过滤 */
    function handleTraceListStatusChange(id: string) {
      traceKind.value = id;
      handleScopeQueryChange();
    }
    /** 字段排序 */
    function handleTraceListSortChange(sortKey: string) {
      traceSortKey.value = sortKey;
      handleScopeQueryChange();
    }
    /** 表头过滤 */
    function handleTraceListColumnFilter(val: Record<string, string[]>) {
      traceColumnFilters.value = val;
      handleScopeQueryChange();
    }
    /* 自动刷新 */
    function handleRefreshIntervalChange(val: number) {
      const fn = () => {
        if (state.searchType === 'accurate') {
          handleQueryTraceId();
        } else if (state.searchType === 'scope') {
          handleScopeQueryChange();
        }
      };
      refreshInterval.value = val;
      clearInterval(refreshIntervalInstance.value);
      if (refreshInterval.value === -1) {
        fn();
        return;
      }
      refreshIntervalInstance.value = setInterval(() => {
        fn();
      }, refreshInterval.value);
      setRouterQueryParams();
    }
    /** 立即刷新 */
    function handleImmediateRefresh() {
      handleClickQuery();
    }
    /** 更多操作 */
    function handleMenuSelectChange() {
      const appName = appList.value?.find(app => app.app_name === state.app)?.app_name || '';
      if (appName) {
        const url = location.href.replace(location.hash, `#/apm/application/config/${appName}`);
        window.open(url, '_blank');
      }
    }
    /** 检查是否带路由参数自动查询 仅限 traceId查询 */
    // 持久化到路由的 conditionList
    const conditionListInQuery = {};
    const checkRouterHasQuery = () => {
      const { search_type: searchType, search_id: searchId = 'traceID' } = route.query;
      if (searchType === 'accurate') {
        // eslint-disable-next-line @typescript-eslint/naming-convention
        const { app_name, trace_id } = route.query;
        if (app_name && trace_id) {
          state.app = app_name as string;
          searchIdType.value = searchId as string;
          traceIDSearchValue.value = trace_id as string;
          handleQueryTraceId();
          handleAppSelectChange(app_name as string);
        }
      } else if (searchType === 'scope') {
        const {
          app_name: appName,
          refreshInterval: interval,
          start_time: startTime,
          end_time: endTime,
          query: keyword,
          duration,
          listType,
          conditionList: conditionListStringify,
        } = route.query;
        state.app = appName as string;
        if (startTime && endTime) {
          timeRange.value = [startTime, endTime] as [string, string];
          curTimestamp.value = handleTransformToTimestamp(timeRange.value);
        }
        if (interval) {
          refreshInterval.value = Number(interval);
          handleRefreshIntervalChange(refreshInterval.value);
        }
        if (keyword?.length) {
          queryString.value = keyword as string;
        }
        if (duration) {
          const [start, end] = duration;
          durationRange.value = [Number(start), Number(end)];
        }
        if (listType) {
          store.setListType(listType as string);
        }
        if (conditionListStringify) {
          const result = JSON.parse(conditionListStringify as string);
          Object.assign(conditionListInQuery, result);
          // 既然有了路由查询参数，就要填上 trace 或 span list 的查询 filter
          Object.keys(result).forEach(key => {
            if (result[key].isInclude && result[key].selectedConditionValue.length) {
              conditionFilter.push({
                key,
                operator: result[key].selectedCondition.value,
                value: result[key].selectedConditionValue,
              });
            }
          });
        }

        setTimeout(() => {
          state.searchType = searchType;
          store.setPageLoading(true);
          handleAppSelectChange(appName as string);
        }, 100);
      }
    };

    // Trace / Span 视角 切换
    function handleListTypeChange() {
      // 将查询参数初始化
      tempSortList.length = 0;
      sortList.length = 0;
      traceColumnFilters.value = {};
      handleClickQuery();
    }

    function handleTraceTypeChange(v: string[]) {
      store.setTraceType(v);
      handleClickQuery();
    }

    function handleSpanTypeChange(v: string[]) {
      store.setSpanType(v);
      handleClickQuery();
    }

    function handleInterfaceStatisticsChange(v: string[]) {
      store.setInterfaceStatisticsType(v);
      handleClickQuery();
    }

    function handleServiceStatisticsChange(v: IServiceStatisticsType) {
      store.setServiceStatisticsType(v);
      handleClickQuery();
    }
    onMounted(() => {
      state.autoQuery = (localStorage.getItem('bk_monitor_auto_query_enable') || 'true') === 'true';
      checkRouterHasQuery();
    });
    onBeforeUnmount(() => {
      destroyTimezone();
    });
    onUnmounted(() => {
      clearInterval(refreshIntervalInstance.value);
    });
    onDeactivated(() => {
      clearInterval(refreshIntervalInstance.value);
    });
    // 查询语句的提示内容
    const tipsContentTpl = () => (
      <div
        id='tips-content'
        class='query-tips-content-wrapper'
      >
        <div class='tips-content-title'>
          {t('可输入SQL语句进行快速查询')}
          <span
            class='link'
            onClick={() => skipToDocsLink('bkLogQueryString')}
          >
            {t('查看语法')}
            <i class='icon-monitor icon-mc-link' />
          </span>
        </div>
        <ul class='tips-content-list'>
          {tipsContentList.map((item, index) => (
            <li
              key={index}
              class='tips-content-item'
            >
              <div class='tips-content-item-label'>{item.label}</div>
              {item.value.map((val, vIndex) => (
                <div
                  key={vIndex}
                  class='tips-content-item-val'
                >
                  {val}
                </div>
              ))}
            </li>
          ))}
        </ul>
      </div>
    );
    const accurateQueryShow = () => (
      <div>
        {formItem(
          (
            <Radio.Group
              v-model={searchIdType.value}
              onChange={handleChangeSearchIdType}
            >
              <Radio label='traceID'>Trace ID</Radio>
              <Radio label='spanID'>Span ID</Radio>
            </Radio.Group>
          ) as any,
          (
            <VerifyInput>
              <Input
                ref={traceIdInput}
                v-model={traceIDSearchValue.value}
                placeholder={t('输入 ID 可精准查询')}
                type='search'
                clearable
                show-clear-only-hover
                onBlur={handleQueryIDInputBlur}
                onEnter={handleQueryTraceId}
              />
            </VerifyInput>
          ) as any
        )}
        <HandleBtn
          accurateQuery={true}
          autoQuery={state.autoQuery}
          canQuery={true}
          onChangeAutoQuery={handleAutoQueryChange}
          onClear={() => {
            traceIDSearchValue.value = '';
            state.isAlreadyAccurateQuery = false;
          }}
          onQuery={handleQueryTraceId}
        />
      </div>
    );

    const isAddConditionButtonLoading = ref(false);

    /**
     * 修改任一条件名称
     * @param index 当前修改的条件下标
     * @param v cascader 的选中值
     */
    const handleItemConditionChange = async (index: number, v: string[]) => {
      // v 在 cascader 会返回一个数组，这里只要最后一个元素
      const LAST_ELEMENT = v[v.length - 1];
      // 修改筛选列表里任意一个条件
      // 需要根据 LAST_ELEMENT 去修改选中值，然后置灰、排序、最后请求对应的候选值。
      const oldLabelValue = conditionList[index].labelValue;
      conditionList[index].labelValue = LAST_ELEMENT;
      conditionList[index].selectedConditionValue.length = 0;
      standardFieldList.value.forEach(item => {
        traverseIds(item, LAST_ELEMENT, true);
        traverseIds(item, oldLabelValue, false);
      });
      // sortStandardFieldList();
      const time = handleTransformToTimestamp(timeRange.value);
      const params = {
        app_name: state.app,
        start_time: time[0],
        end_time: time[1],
        bk_biz_id: window.bk_biz_id,
        fields: [LAST_ELEMENT],
      };
      conditionList[index].conditionValueList.length = 0;
      isAddConditionButtonLoading.value = true;
      if (!params.app_name) return; // 无应用时不调用getFieldOptionValues API
      const result = await getFieldOptionValues(params)
        .catch(() => {})
        .finally(() => (isAddConditionButtonLoading.value = false));
      conditionList[index].conditionValueList = result[LAST_ELEMENT];
    };

    const handleConditionDelete = (index: number, id: string) => {
      const oldConditionList = [...conditionList];
      const hasValueCondition = oldConditionList[index]?.selectedConditionValue?.length;
      conditionList.splice(index, 1);
      // 将置灰的选项变回可选
      standardFieldList.value.forEach(item => {
        traverseIds(item, id, false);
      });
      // 然后还要排序把可选的提上去
      // sortStandardFieldList();

      if (state.autoQuery && hasValueCondition) {
        handleSelectComplete(true);
      }
    };

    const handleIncludeChange = (index: number) => {
      conditionList[index].isInclude = !conditionList[index].isInclude;
      if (state.autoQuery && conditionList[index]?.selectedConditionValue?.length) {
        handleSelectComplete(true);
      }
    };

    const handleConditionChange = (index: number, v: any) => {
      conditionList[index].selectedCondition = v;
    };

    const handleDurationRangeChange = (index: number, v: number) => {
      conditionList[index].durationRange = v;
    };

    const selectedConditions = ref([]);

    const standardFieldList = ref([]);
    const getStandardFields = async () => {
      const result = await listStandardFilterFields({}, { cancelToken: cancelTokenSource?.token }).catch(() => {});

      result?.map(item => (item.disabled = false));
      standardFieldList.value = result;
      setDefaultConditionList();
    };
    // 只有在 范围查询 才获取标准字段
    // TODO：这里由于执行顺序的问题，导致 state.searchType 在这里一直是 'accurate' 这里先用路由参数
    if (state.searchType === 'scope' || route.query.search_type === 'scope') getStandardFields();

    // 页面需要有默认筛选项显示，现在仅通过前端的方式去展示。
    const setDefaultConditionList = () => {
      let defaultShowCondition = [];
      // 如果路由有持久化 conditionList ，就不用加载默认项了。
      if (Object.keys(conditionListInQuery).length) {
        defaultShowCondition = Object.keys(conditionListInQuery);
      } else {
        defaultShowCondition = ['resource.service.name', 'span_name'];
      }
      selectedConditions.value = defaultShowCondition;
      // 初始化条件要置灰
      selectedConditions.value.forEach(targetID => {
        standardFieldList.value?.forEach(item => {
          traverseIds(item, targetID, true);
        });
      });
      handleConditionBlur();
    };

    // const sortStandardFieldList = () => {
    //   // TODO: 该排序还有点细节需要调整。
    //   standardFieldList.value.sort((next, prev) => (prev.disabled ? -1 : 0));
    // };

    const cascaderSelectedValue = ref([]);
    const handleCascaderChange = () => {
      // 只要选中的最后一个值，中间值统统不要。
      selectedConditions.value = [cascaderSelectedValue.value[cascaderSelectedValue.value.length - 1]];
      handleConditionBlur();
    };

    // 递归遍历置灰
    const traverseIds = (obj: any, targetID: string, disableType: boolean) => {
      if (obj.id === targetID) {
        obj.disabled = disableType;
      }
      if (obj.children) {
        obj.children.forEach(childObj => {
          traverseIds(childObj, targetID, disableType);
        });
      }
    };

    const handleConditionBlur = async () => {
      // 置灰
      const targetID = selectedConditions.value[0];
      standardFieldList.value?.forEach(item => {
        traverseIds(item, targetID, true);
      });
      // 需要把已选过的置灰，然后放在最底部。
      // sortStandardFieldList();

      // 向后端发起请求 条件名称 和 对应的候选值
      const time = handleTransformToTimestamp(timeRange.value);
      const params = {
        app_name: state.app,
        start_time: time[0],
        end_time: time[1],
        bk_biz_id: window.bk_biz_id,
        fields: selectedConditions.value,
      };
      // 没有选择或配置正确的筛选项就不应该发生请求 || 无应用时不调用getFieldOptionValues API。
      if (params.fields.length === 0 || !params.app_name) return;
      isAddConditionButtonLoading.value = true;
      const result = await getFieldOptionValues(params, { cancelToken: cancelTokenSource?.token })
        .catch(() => {})
        .finally(() => (isAddConditionButtonLoading.value = false));
      selectedConditions.value.length = 0;

      // 添加条件列表
      for (const key of Object.keys(result || {})) {
        const singleCondition = {
          selectedCondition: {
            label: '=',
            value: 'equal',
          },
          isInclude: true,
          labelValue: key,
          labelList: standardFieldList.value,
          conditionType: 'select',
          conditionList: [
            {
              label: '=',
              value: 'equal',
            },
            {
              label: '!=',
              value: 'not_equal',
            },
            {
              label: 'exists',
              value: 'exists',
            },
            {
              label: 'not exists',
              value: 'not exists',
            },
          ],
          selectedConditionValue: [],
          conditionValueList: result[key],
        };
        if (conditionListInQuery[key]) Object.assign(singleCondition, conditionListInQuery[key]);
        conditionList.push(singleCondition);
      }
    };

    const handleConditionValueChange = (index, v) => {
      conditionList[index].selectedConditionValue = v;
    };

    const handleConditionValueClear = (index: number) => {
      conditionList[index].selectedConditionValue.length = 0;
      handleSelectComplete(true);
    };

    /**
     * @desc 复选框的值发生变化
     * @param { Boolean } isManual 是否手动删除或关闭开关调用
     * TODO: 其实不应该通过一个参数去控制是否继续去发起请求
     */
    const handleSelectComplete = (isManual = false) => {
      collectConditionFilter();
      // 没有筛选项，就不用请求
      // if (!isManual && conditionFilter.length === 0) return;
      if (!isManual) return;
      // 检查侧边栏的 条件 是否发生变化。
      if (checkHasRepeatConditionValue()) return;
      handleScopeQueryChange();
    };

    // 上次请求的所带上的 条件 ，用作对比前后的条件是否都相等，如相等就不应该再发起请求。
    let lastCollectConditionFilter: any[] | null = null;
    // 重新收集左侧条件列表
    const collectConditionFilter = () => {
      // 先保存一份旧的条件列表。
      lastCollectConditionFilter = deepClone(conditionFilter);
      conditionFilter.length = 0;
      // 把 conditionList 中所需要的数据统统
      // 如果 isInclude (是否参与筛选) 为选中 和 操作符未选择，都不参与请求
      conditionList.forEach(item => {
        // 选择参与筛选和有选择了候选值才参与请求
        if (item.isInclude && item.selectedConditionValue.length) {
          conditionFilter.push({
            key: item.labelValue,
            operator: item.selectedCondition?.value,
            value: item.selectedConditionValue,
          });
        }
      });
    };

    // 在 onBlue 事件后检查前后两次条件列表的内容是否相等，避免重复请求。
    // 这里不能使用 watch 作为监听方式，因为选项顺序的改变也会触发 watch 回调，而在这里不需要考虑顺序问题。
    const checkHasRepeatConditionValue = (): boolean => {
      let isRepeatConditionValue = true;
      // 前后选择的条件不同，不需要再对比。
      if (lastCollectConditionFilter.length !== conditionFilter.length) return (isRepeatConditionValue = false);
      conditionFilter.forEach((item: any) => {
        const target = lastCollectConditionFilter.find(lastFilterItem => lastFilterItem.key === item.key);
        // 如果没找到原先的条件，说明有新增。
        if (!target) isRepeatConditionValue = false;
        // 操作符 或 所选的值(这个是数组，即使内容都相等，但是可能顺序不同，所以需要 sort 再 toString 去比较)
        if (!(target.operator === item.operator && target.value.sort().toString() === item.value.sort().toString())) {
          isRepeatConditionValue = false;
        }
      });
      return isRepeatConditionValue;
    };

    const scopeQueryShow = () => (
      <div>
        {formItem(
          (
            <div>
              <span>{t('查询语句')}</span>
              <Popover
                width='256'
                v-slots={{
                  content: () => tipsContentTpl(),
                }}
                placement='bottom-start'
                theme='light'
                trigger='click'
              >
                <span class='icon-monitor icon-mc-help-fill' />
              </Popover>
            </div>
          ) as any,
          (
            <VerifyInput>
              <Input
                style='min-height: 70px;'
                v-model={queryString.value}
                placeholder={t('输入')}
                type='textarea'
                autosize
                onBlur={() => handleScopeQueryChange(false)}
              />
            </VerifyInput>
          ) as any
        )}
        {formItem(
          (
            <span>
              {t('耗时')}
              <span class='label-tips'>{`（${t('支持')} ns, μs, ms, s, m, h, d）`}</span>
            </span>
          ) as any,
          (
            <DurationFilter
              range={durationRange.value ?? undefined}
              onChange={handleDurationChange}
            />
          ) as any
        )}
        {/* 这里插入 condition 组件 */}
        {conditionList.map((item, index) => (
          <Condition
            key={item.labelValue}
            style='margin-bottom: 16px;'
            conditionList={item.conditionList}
            conditionType={item.conditionType}
            conditionValueList={item.conditionValueList}
            durationRange={item.durationRange}
            isInclude={item.isInclude}
            labelList={item.labelList}
            labelValue={item.labelValue}
            selectedCondition={item.selectedCondition}
            selectedConditionValue={item.selectedConditionValue}
            onConditionChange={v => handleConditionChange(index, v)}
            onConditionValueChange={v => handleConditionValueChange(index, v)}
            onConditionValueClear={() => handleConditionValueClear(index)}
            onDelete={id => handleConditionDelete(index, id)}
            onDurationRangeChange={v => handleDurationRangeChange(index, v)}
            onIncludeChange={() => handleIncludeChange(index)}
            onItemConditionChange={v => handleItemConditionChange(index, v)}
            onSelectComplete={() => handleSelectComplete(true)}
          />
        ))}
        {/* 这里是 添加条件 按钮 */}
        <div class='inquire-cascader-container'>
          <Button
            class='add-condition'
            loading={isAddConditionButtonLoading.value}
            theme='primary'
          >
            <i
              style='margin-right: 6px;'
              class='icon-monitor icon-plus-line'
            />
            <span>{t('添加条件')}</span>
          </Button>

          <Cascader
            class='inquire-cascader'
            v-model={cascaderSelectedValue.value}
            disabled={isAddConditionButtonLoading.value}
            list={standardFieldList.value}
            onChange={handleCascaderChange}
          />
        </div>
        <HandleBtn
          autoQuery={state.autoQuery}
          canQuery={true}
          onAdd={handleAddCollect}
          onChangeAutoQuery={handleAutoQueryChange}
          onClear={handleClearQuery}
          onQuery={handleClickQuery}
        />
      </div>
    );
    expose({ autoQueryPopover });
    const renderFn = () => (
      <div class='inquire-main'>
        <div
          class='inquire-left'
          v-monitor-drag={{
            theme: 'simple',
            minWidth: 200,
            maxWidth: 800,
            defaultWidth: leftDefaultWidth,
            autoHidden: true,
            isShow: state.showLeft,
            onHidden: () => handleLeftHiddenAndShow(false),
            onWidthChange: (width: number) => (state.leftWidth = width),
          }}
        >
          <div class={['inquire-left-main', { 'scope-inquire': state.searchType === 'scope' }]}>
            <div class='left-top'>
              <div class='left-title'>{t('route-Tracing 检索')}</div>
              <div class='left-title-operate'>
                <span
                  class='icon-monitor icon-double-down'
                  onClick={() => handleLeftHiddenAndShow(false)}
                />
              </div>
            </div>
            {/* 查询操作表单 */}
            <div class={['query-container', { 'scope-query-container': state.searchType === 'scope' }]}>
              <SearchLeft
                v-models={[
                  [state.app, 'app'],
                  [state.searchType, 'searchType'],
                ]}
                v-slots={{
                  query: () => (state.searchType === 'accurate' ? accurateQueryShow() : scopeQueryShow()),
                }}
                appList={appList.value}
                showBottom={state.searchType === 'scope'}
                onAddCondition={handleAddCondition}
                onAppChange={val => handleAppSelectChange(val, true)}
                onSearchTypeChange={handleSearchTypeChange}
              />
            </div>
          </div>
        </div>
        <div
          style={{ flex: 1, width: `calc(100% - ${state.leftWidth}px)` }}
          class='inquire-right'
        >
          {/* <Loading
            class='inquire-page-loading'
            loading={isLoading.value}
          > */}
          {/* 头部工具栏 */}
          <SearchHeader
            style={{ height: `${HEADER_HEIGHT}px` }}
            class='inquire-right-header'
            v-models={[
              [state.showLeft, 'showLeft'],
              [refreshInterval.value, 'refreshInterval'],
              [timeRange.value, 'timeRange'],
              [timezone.value, 'timezone'],
            ]}
            checkedValue={collectCheckValue.value}
            favoritesList={collectList.value}
            menuList={headerToolMenuList}
            onDeleteCollect={handleDeleteCollect}
            onImmediateRefresh={handleImmediateRefresh}
            onMenuSelectChange={handleMenuSelectChange}
            onRefreshIntervalChange={handleRefreshIntervalChange}
            onSelectCollect={handleSelectCollect}
            onTimeRangeChange={handleTimeRangeChange}
            onTimezoneChange={handleTimezoneChange}
          />
          <div
            style={{ height: `calc(100% - ${HEADER_HEIGHT}px)` }}
            class='inquire-right-main'
          >
            <InquireContent
              appList={appList.value}
              appName={state.app}
              emptyApp={isEmptyApp.value}
              isAlreadyAccurateQuery={state.isAlreadyAccurateQuery}
              isAlreadyScopeQuery={state.isAlreadyScopeQuery}
              queryType={state.searchType}
              searchIdType={searchResultIdType.value}
              spanDetails={spanDetails.value}
              traceColumnFilters={cacheTraceColumnFilters.value}
              traceListTableLoading={traceListTableLoading.value}
              onChangeQuery={val => handleChangeQuery(val)}
              onInterfaceStatisticsChange={handleInterfaceStatisticsChange}
              onListTypeChange={handleListTypeChange}
              onServiceStatisticsChange={handleServiceStatisticsChange}
              onSpanTypeChange={handleSpanTypeChange}
              onTraceListColumnFilter={handleTraceListColumnFilter}
              onTraceListColumnSortChange={value => handleTraceListColumnSort(value)}
              onTraceListScrollBottom={handleTraceListScrollBottom}
              onTraceListSortChange={handleTraceListSortChange}
              onTraceListStatusChange={handleTraceListStatusChange}
              onTraceTypeChange={handleTraceTypeChange}
            />
          </div>
          {/* </Loading> */}
        </div>
        <Dialog
          v-slots={{
            default: () => (
              <DeleteDialogContent
                name={collectDialog.name}
                subtitle={t('收藏名')}
                title={t('确认删除该收藏？')}
              />
            ),
          }}
          footerAlign={'center'}
          isLoading={collectDialog.loading}
          isShow={collectDialog.show}
          title={''}
          onClosed={() => {
            collectDialog.show = false;
          }}
          onConfirm={() => deleteCollect()}
        />
      </div>
    );
    return {
      state,
      timeRange,
      renderFn,
      selectedConditions,
      standardFieldList,
      conditionList,
    };
  },
  render() {
    return this.renderFn();
  },
});
