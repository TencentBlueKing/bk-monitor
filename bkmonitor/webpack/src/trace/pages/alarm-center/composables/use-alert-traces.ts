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

import { type MaybeRef, reactive, shallowRef, watch, onScopeDispose } from 'vue';

import { get } from '@vueuse/core';
import { alertTraces } from 'monitor-api/modules/alert_v2';

import { ExploreTableLoadingEnum } from '@/pages/trace-explore/components/trace-explore-table/typing';
import { useAlarmCenterDetailStore } from '@/store/modules/alarm-center-detail';

import type { ALertTracesData, ALertTracesQueryConfig } from '../typings';

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

  const error = shallowRef(false);
  let requestId = 0;
  const getTraceList = async () => {
    if (!get(alertId)) return;
    const current = ++requestId;
    const offset = pagination.offset;
    const state = offset ? ExploreTableLoadingEnum.SCROLL : ExploreTableLoadingEnum.BODY_SKELETON;
    error.value = false;
    tableLoading[state] = true;
    try {
      const data: ALertTracesData = await alertTraces({
        alert_id: get(alertId), offset, limit: pagination.limit,
        bk_biz_id: alarmCenterDetailStore.bizId,
      });
      if (current !== requestId) return;
      traceList.value = offset ? [...traceList.value, ...data.list] : data.list;
      traceQueryConfig.value = data.query_config;
      tableHasMoreData.value = data.list?.length >= pagination.limit;
    } catch {
      if (current === requestId) error.value = true;
    } finally {
      if (current === requestId) tableLoading[state] = false;
    }
  };
  const loadMore = () => {
    if (error.value || !tableHasMoreData.value || Object.values(tableLoading).some(Boolean)) return;
    pagination.offset = traceList.value.length;
    getTraceList();
  };
  watch([() => get(alertId), () => alarmCenterDetailStore.bizId], () => {
    pagination.offset = 0;
    traceList.value = [];
    tableLoading[ExploreTableLoadingEnum.SCROLL] = false;
    getTraceList();
  }, { immediate: true });
  onScopeDispose(() => { ++requestId; });

  return {
    error, retry: getTraceList, loadMore,
    traceList,
    traceQueryConfig,
    tableLoading,
    pagination,
    tableHasMoreData,
  };
};
