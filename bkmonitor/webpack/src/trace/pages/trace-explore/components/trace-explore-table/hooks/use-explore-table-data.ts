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

import { get, useDebounceFn } from '@vueuse/core';
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
  const { commonParams, sourceFieldConfigs, onBackTop } = options;

  const store = useTraceExploreStore();
  const {
    mode,
    appName,
    timeRange,
    refreshImmediate,
    filterTableList,
    tableList: tableData,
    tableSortContainer: sortContainer,
  } = storeToRefs(store);

  /** 表格单页条数 */
  const limit = 30;
  /** 表格logs数据请求中止控制器 */
  let abortController: AbortController = null;

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

  /** 请求参数 */
  const queryParams = computed(() => {
    const params = get(commonParams);
    // eslint-disable-next-line @typescript-eslint/naming-convention
    const { mode: _mode, query_string, ...restParams } = params;
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
    if (abortController) {
      abortController.abort();
      abortController = null;
    }
    // eslint-disable-next-line @typescript-eslint/naming-convention
    const { app_name, start_time, end_time } = queryParams.value;
    if (!app_name || !start_time || !end_time) {
      store.updateTableList([]);
      tableLoading[ExploreTableLoadingEnum.HEADER_SKELETON] = false;
      tableLoading[ExploreTableLoadingEnum.BODY_SKELETON] = false;
      tableLoading[ExploreTableLoadingEnum.SCROLL] = false;
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
    if (loadingType === ExploreTableLoadingEnum.BODY_SKELETON) {
      store.updateTableList([]);
    }

    tableLoading[loadingType] = true;
    store.updateTableLoading(true);
    const requestParam = {
      ...queryParams.value,
      limit: limit,
      offset: tableData.value?.length || 0,
    };
    abortController = new AbortController();
    const res = await getTableList(requestParam, isSpanVisual.value, {
      signal: abortController.signal,
    });
    store.updateTableLoading(false);
    if (res?.isAborted) {
      tableLoading[ExploreTableLoadingEnum.SCROLL] = false;
      return;
    }
    tableLoading[loadingType] = false;
    tableLoading[ExploreTableLoadingEnum.HEADER_SKELETON] = false;
    // 更新表格数据
    if (loadingType === ExploreTableLoadingEnum.BODY_SKELETON) {
      store.updateTableList(res.data);
    } else {
      store.updateTableList([...tableData.value, ...res.data]);
    }
    tableHasMoreData.value = res.data?.length >= limit;
  };

  const debouncedGetExploreList = useDebounceFn(getExploreList, 200);

  // 监听参数变化，自动刷新数据
  watch(
    [
      () => isSpanVisual.value,
      () => get(appName),
      () => get(timeRange),
      () => get(refreshImmediate),
      () => get(sortContainer).sortBy,
      () => get(sortContainer).descending,
      () => get(commonParams)?.filters,
      () => get(commonParams)?.query_string,
    ],
    (nVal, oVal) => {
      onBackTop?.();
      tableLoading[ExploreTableLoadingEnum.BODY_SKELETON] = true;
      tableLoading[ExploreTableLoadingEnum.HEADER_SKELETON] = true;
      store.updateTableList([]);

      if (nVal[0] !== oVal[0] || nVal[1] !== oVal[1]) {
        handleSortChange({
          sortBy: '',
          descending: null,
        });
      }
      debouncedGetExploreList();
    }
  );

  onBeforeUnmount(() => {
    abortController?.abort?.();
    abortController = null;
    store.updateTableList([]);
    store.updateTableSortContainer({ sortBy: '', descending: null });
  });

  return {
    getExploreList,
    handleSortChange,
    sortContainer,
    tableHasScrollLoading,
    tableLoading,
    tableViewData,
  };
};
