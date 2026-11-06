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
import { type ComputedRef, type MaybeRef, type Ref, computed, onBeforeUnmount, reactive, shallowRef, watch } from 'vue';

import { get } from '@vueuse/core';
import { storeToRefs } from 'pinia';

import { handleTransformToTimestamp } from '../../../../../components/time-range/utils';
import { useTraceExploreStore } from '../../../../../store/modules/explore';
import { ExploreTableLoadingEnum } from '../typing';
import { getTableList } from '../utils/api-utils';

import type { ISpanListItem, ITraceListItem } from '../../../../../typings';
import type { ICommonParams, IDimensionField } from '../../../typing';
import type { SortInfo, TableSort } from '@blueking/tdesign-ui';

export interface UseExploreTableDataOptions {
  /** 接口请求配置参数 */
  commonParams: MaybeRef<ICommonParams>;
  ready: MaybeRef<boolean>;
  /** 表格所有列字段配置数组(接口原始结构) */
  sourceFieldConfigs: MaybeRef<IDimensionField[]>;
  /** 回到顶部回调 */
  onBackTop?: () => void;
}

export interface UseExploreTableDataReturn {
  /** 表格列排序配置 */
  sortContainer: Ref<SortInfo>;
  /** 判断当前数据是否需要触底加载更多 */
  tableHasScrollLoading: ComputedRef<boolean>;
  tableRefreshing: ComputedRef<boolean>;
  /** 当前表格需要渲染的数据(根据图标耗时统计面板过滤后的数据) */
  tableViewData: ComputedRef<ISpanListItem[] | ITraceListItem[]>;
  /** 获取表格数据 */
  getExploreList: (loadingType?: ExploreTableLoadingEnum) => Promise<void>;
  /** 排序变化处理 */
  handleSortChange: (sortEvent: TableSort) => void;
  /** table loading 配置 */
  tableLoading: {
    [ExploreTableLoadingEnum.BODY_SKELETON]: boolean;
    [ExploreTableLoadingEnum.HEADER_SKELETON]: boolean;
    [ExploreTableLoadingEnum.SCROLL]: boolean;
  };
}

/**
 * @description Explore 表格数据管理 Hook
 * 用于管理表格数据的获取、缓存、排序等逻辑
 * @param options 配置选项
 */
export const useExploreTableData = (options: UseExploreTableDataOptions): UseExploreTableDataReturn => {
  const { commonParams, sourceFieldConfigs, ready, onBackTop } = options;

  const store = useTraceExploreStore();
  const {
    mode,
    appName,
    timeRange,
    timezone,
    refreshImmediate,
    filterTableList,
    tableList: tableData,
    tableSortContainer: sortContainer,
  } = storeToRefs(store);

  /** 表格单页条数 */
  const limit = 30;
  /** 表格logs数据请求中止控制器 */
  let abortController: AbortController = null;
  let requestId = 0;
  let disposed = false;
  let queryTimer: ReturnType<typeof setTimeout>;
  const pending = shallowRef(false);

  /** 判断table数据是否还有数据可以获取 */
  const tableHasMoreData = shallowRef(false);
  /** table loading 配置 */
  const tableLoading = reactive({
    /** table body部分 骨架屏 loading */
    [ExploreTableLoadingEnum.BODY_SKELETON]: false,
    /** table header部分 骨架屏 loading */
    [ExploreTableLoadingEnum.HEADER_SKELETON]: false,
    /** 表格触底加载更多 loading  */
    [ExploreTableLoadingEnum.SCROLL]: false,
  });

  /** 当前视角是否为 Span 视角 */
  const isSpanVisual = computed(() => get(mode) === 'span');
  /** 当前是否进行了本地 "耗时" 的筛选操作 */
  const isLocalFilterMode = computed(() => {
    const filterList = get(filterTableList);
    return filterList?.length > 0;
  });
  /** 当前表格需要渲染的数据(根据图标耗时统计面板过滤后的数据) */
  const tableViewData = computed(() => (isLocalFilterMode.value ? get(filterTableList) : tableData.value));
  /** 判断当前数据是否需要触底加载更多 */
  const tableHasScrollLoading = computed(() => !isLocalFilterMode.value && tableHasMoreData.value);
  const tableRefreshing = computed(
    () =>
      pending.value &&
      !tableLoading[ExploreTableLoadingEnum.BODY_SKELETON] &&
      !tableLoading[ExploreTableLoadingEnum.SCROLL]
  );

  const finishLoading = () => {
    pending.value = false;
    store.updateTableLoading(false);
    tableLoading[ExploreTableLoadingEnum.BODY_SKELETON] = false;
    tableLoading[ExploreTableLoadingEnum.HEADER_SKELETON] = false;
    tableLoading[ExploreTableLoadingEnum.SCROLL] = false;
  };

  /** 请求参数 */
  const queryParams = computed(() => {
    const params = get(commonParams);
    // eslint-disable-next-line @typescript-eslint/naming-convention
    const { mode: _mode, query_string, ...restParams } = params;
    // timezone 影响绝对时间 unix 转换，需纳入 computed 依赖
    void get(timezone);
    const [startTime, endTime] = handleTransformToTimestamp(get(timeRange));

    let sort: string[] = [];
    if (get(sortContainer).sortBy) {
      sort = [`${get(sortContainer).descending ? '-' : ''}${get(sortContainer).sortBy}`];
    }

    return {
      ...restParams,
      start_time: startTime,
      end_time: endTime,
      query: query_string,
      sort,
    };
  });

  /**
   * @description 表格排序回调
   * @param sortEvent.sortBy 排序字段名
   * @param sortEvent.descending 排序方式
   */
  const handleSortChange = (sortEvent: TableSort) => {
    if (Array.isArray(sortEvent)) {
      return;
    }
    store.updateTableSortContainer(sortEvent);
  };

  /**
   * @description: 获取 table 表格数据
   */
  const getExploreList = async (loadingType = ExploreTableLoadingEnum.BODY_SKELETON) => {
    if (disposed || !get(ready)) return;
    const isScroll = loadingType === ExploreTableLoadingEnum.SCROLL;
    if (isScroll && (pending.value || !tableHasScrollLoading.value)) {
      return;
    }
    const currentRequest = ++requestId;
    if (abortController) {
      abortController.abort();
      abortController = null;
    }
    // eslint-disable-next-line @typescript-eslint/naming-convention
    const { app_name, start_time, end_time } = queryParams.value;
    if (!app_name || !start_time || !end_time) {
      store.updateTableList([]);
      tableHasMoreData.value = false;
      finishLoading();
      return;
    }

    // 获取字段配置，构建 fieldMap
    const fieldConfigs = get(sourceFieldConfigs) ?? [];
    const fieldMap: Record<string, IDimensionField> = {};
    for (const curr of fieldConfigs) {
      if (curr.can_displayed) {
        fieldMap[curr.name] = curr;
      }
    }

    // 检测排序字段是否在字段列表中，不在则忽略该字段的排序规则
    const shouldIgnoreSortField = get(sortContainer).sortBy && !fieldMap[get(sortContainer).sortBy];
    if (shouldIgnoreSortField) {
      handleSortChange({ sortBy: '', descending: null });
      return;
    }
    tableLoading[ExploreTableLoadingEnum.SCROLL] = isScroll;
    tableLoading[ExploreTableLoadingEnum.BODY_SKELETON] = !isScroll && !tableData.value.length;
    pending.value = true;
    store.updateTableLoading(true);
    const requestParam = {
      ...queryParams.value,
      limit: limit,
      offset: isScroll ? tableData.value.length : 0,
    };
    abortController = new AbortController();
    const res = await getTableList(requestParam, isSpanVisual.value, {
      signal: abortController.signal,
    });
    if (disposed || currentRequest !== requestId) return;
    finishLoading();
    if (res?.isAborted) {
      return;
    }
    if (res.isError) return;
    // 更新表格数据
    if (!isScroll) {
      store.updateFilterTableList([]);
      store.updateTableList(res.data);
    } else {
      store.updateTableList([...tableData.value, ...res.data]);
    }
    tableHasMoreData.value = res.data?.length >= limit;
  };

  const searchKey = computed(() =>
    JSON.stringify([get(commonParams), get(timeRange), get(timezone), get(sortContainer), get(mode), get(appName)])
  );

  watch([() => get(mode), () => get(appName)], () => {
    handleSortChange({ sortBy: '', descending: null });
  });

  // 监听参数变化，自动刷新数据
  watch(
    [() => searchKey.value, () => get(ready), () => get(commonParams), () => get(refreshImmediate)],
    (nVal, oVal) => {
      requestId += 1;
      abortController?.abort();
      clearTimeout(queryTimer);
      const changed = nVal[0] !== oVal?.[0];
      if (changed) {
        onBackTop?.();
        store.updateTableList([]);
        store.updateFilterTableList([]);
        tableHasMoreData.value = false;
      }
      pending.value = true;
      store.updateTableLoading(true);
      tableLoading[ExploreTableLoadingEnum.BODY_SKELETON] = !tableData.value.length;
      tableLoading[ExploreTableLoadingEnum.HEADER_SKELETON] = !get(ready);
      tableLoading[ExploreTableLoadingEnum.SCROLL] = false;
      if (get(ready)) queryTimer = setTimeout(() => getExploreList(), 200);
    },
    { immediate: true }
  );

  onBeforeUnmount(() => {
    disposed = true;
    requestId += 1;
    clearTimeout(queryTimer);
    abortController?.abort?.();
    abortController = null;
    finishLoading();
    store.updateTableList([]);
    store.updateTableSortContainer({ sortBy: '', descending: null });
  });

  return {
    getExploreList,
    handleSortChange,
    sortContainer,
    tableHasScrollLoading,
    tableRefreshing,
    tableLoading,
    tableViewData,
  };
};
