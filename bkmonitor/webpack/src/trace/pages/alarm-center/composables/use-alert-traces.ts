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

import { type MaybeRef, computed, reactive, shallowRef, watch } from 'vue';

import { get } from '@vueuse/core';
import { alertTraces } from 'monitor-api/modules/alert_v2';

import { EMode } from '@/components/retrieval-filter/typing';
// 【临时联调 mock，联调就绪后删除本行 import 与下方 filterRowsByPanelFilterMock / filterRowsBySourceMock 调用】
import { filterRowsByPanelFilterMock, filterRowsBySourceMock } from '@/mock/alarm-detail-panel-filter';
import { ExploreTableLoadingEnum } from '@/pages/trace-explore/components/trace-explore-table/typing';
import { useAlarmCenterDetailStore } from '@/store/modules/alarm-center-detail';

import type { ALertTracesData, ALertTracesQueryConfig } from '../typings';
import type { IWhereItem } from '@/components/retrieval-filter/typing';

/**
 * @function useAlertTraces 调用链数据 hook
 * @description 告警详情 - 调用链 - 表格数据获取及相关的处理逻辑
 * @param {MaybeRef<string>} alertId 告警ID
 */
export const useAlertTraces = (alertId: MaybeRef<string>) => {
  const alarmCenterDetailStore = useAlarmCenterDetailStore();

  /** 调用链表格展示数据 */
  const traceList = shallowRef([]);
  /** 调用链查询配置 */
  const traceQueryConfig = shallowRef<ALertTracesQueryConfig>({
    app_name: '',
    sceneMode: '',
    where: [],
  });
  /** table loading 配置 */
  const tableLoading = reactive({
    /** table body部分 骨架屏 loading */
    [ExploreTableLoadingEnum.BODY_SKELETON]: false,
    /** table header部分 骨架屏 loading */
    [ExploreTableLoadingEnum.HEADER_SKELETON]: false,
    /** 表格触底加载更多 loading  */
    [ExploreTableLoadingEnum.SCROLL]: false,
  });

  const pagination = reactive({
    offset: 0,
    limit: 30,
  });

  /** 判断当前数据是否需要触底加载更多 */
  const tableHasMoreData = shallowRef(true);

  /** 筛选模式：UI / 语句 */
  const filterMode = shallowRef<EMode>(EMode.ui);
  /** UI 模式筛选条件，格式与 trace 检索接口的 filters 一致 */
  const where = shallowRef<IWhereItem[]>([]);
  /** 语句模式筛选条件 */
  const queryString = shallowRef('');
  /** 条件没变但用户又点了一次搜索时，靠它触发重新请求 */
  const searchKey = shallowRef(0);
  /** 用户手动切换的应用，空值表示跟随告警自身关联的应用 */
  const selectedAppName = shallowRef('');

  /** 告警维度里的 app_name，接口 query_config 缺失时兜底 */
  const dimensionAppName = computed(() => {
    const dims = alarmCenterDetailStore.alarmDetail?.dimensions || [];
    return dims.find(item => item.key === 'app_name')?.value || '';
  });

  /** 当前查询的应用：用户选过 > 接口返回 > 告警维度 */
  const currentAppName = computed(
    () => selectedAppName.value || traceQueryConfig.value?.app_name || dimensionAppName.value || ''
  );

  /** 影响请求结果的全部入参，任一变化都重新拉数据 */
  const queryParams = computed(() => ({
    alertId: get(alertId),
    bizId: alarmCenterDetailStore.bizId,
    offset: pagination.offset,
    limit: pagination.limit,
    filterMode: filterMode.value,
    where: where.value,
    queryString: queryString.value,
    searchKey: searchKey.value,
    appName: selectedAppName.value,
  }));

  /**
   * @method getTraceList 请求接口
   * @description 获取调用链表格数据
   */
  const getTraceList = async () => {
    const { alertId: currentAlertId, bizId, offset, limit, filterMode: currentMode } = queryParams.value;
    const { where: currentWhere, queryString: currentQueryString } = queryParams.value;
    if (!currentAlertId) return;
    const isUiMode = currentMode === EMode.ui;
    if (offset === 0) {
      tableLoading[ExploreTableLoadingEnum.BODY_SKELETON] = true;
    } else {
      tableLoading[ExploreTableLoadingEnum.SCROLL] = true;
    }
    const data: ALertTracesData = await alertTraces({
      alert_id: currentAlertId,
      offset,
      limit,
      bk_biz_id: bizId,
      // 【待后端支持】alert/traces 目前忽略 app_name / filters / query_string，联调完成前由 mock 在前端模拟
      app_name: currentAppName.value,
      filters: isUiMode ? currentWhere : [],
      query_string: isUiMode ? '' : currentQueryString,
    }).catch(() => ({ list: [], query_config: traceQueryConfig.value }));
    // 【临时联调 mock，联调就绪后删除这两段，直接用 data.list】
    const originAppName = data.query_config?.app_name || dimensionAppName.value || '';
    const rows = filterRowsBySourceMock(
      data.list || [],
      !selectedAppName.value || selectedAppName.value === originAppName
    );
    const list = filterRowsByPanelFilterMock(rows, {
      filterMode: currentMode,
      where: currentWhere,
      queryString: currentQueryString,
      getFieldValue: (row, key) => row?.[key],
      getAllValues: row => Object.values(row || {}),
    });
    if (pagination.offset === 0) {
      traceList.value = list;
      tableLoading[ExploreTableLoadingEnum.BODY_SKELETON] = false;
    } else {
      traceList.value = [...traceList.value, ...list];
      tableLoading[ExploreTableLoadingEnum.SCROLL] = false;
    }
    traceQueryConfig.value = data.query_config;
    // 按接口原始返回条数判断，避免 mock 过滤后误判到底
    tableHasMoreData.value = data.list?.length >= pagination.limit;
  };

  /** 筛选条件变化后从第一页重新查 */
  const resetPagination = () => {
    pagination.offset = 0;
  };

  const handleWhereChange = (val: IWhereItem[]) => {
    where.value = val;
    resetPagination();
  };

  const handleQueryStringChange = (val: string) => {
    queryString.value = val;
    resetPagination();
  };

  const handleFilterModeChange = (mode: EMode) => {
    filterMode.value = mode;
    if (mode === EMode.ui) {
      queryString.value = '';
    } else {
      where.value = [];
    }
    resetPagination();
  };

  const handleSearch = () => {
    resetPagination();
    searchKey.value += 1;
  };

  /** 切换应用后原有筛选条件的字段可能不存在，一并清空 */
  const handleAppNameChange = (appName: string) => {
    selectedAppName.value = appName;
    where.value = [];
    queryString.value = '';
    resetPagination();
  };

  /** 诊断面板灌入的外部筛选：可同时切应用与 where，不清空对方已指定的条件 */
  const applyExternalFilter = (filter: {
    appName?: string;
    filterMode?: EMode;
    queryString?: string;
    where?: IWhereItem[];
  }) => {
    if (filter.appName) {
      selectedAppName.value = filter.appName;
    }
    const mode = filter.filterMode ?? EMode.ui;
    filterMode.value = mode;
    if (mode === EMode.queryString) {
      queryString.value = filter.queryString || '';
      where.value = [];
    } else {
      where.value = filter.where || [];
      queryString.value = '';
    }
    resetPagination();
    searchKey.value += 1;
  };

  watch(queryParams, getTraceList, { immediate: true });

  return {
    traceList,
    traceQueryConfig,
    currentAppName,
    tableLoading,
    pagination,
    tableHasMoreData,
    filterMode,
    where,
    queryString,
    handleWhereChange,
    handleQueryStringChange,
    handleFilterModeChange,
    handleAppNameChange,
    applyExternalFilter,
    handleSearch,
  };
};
