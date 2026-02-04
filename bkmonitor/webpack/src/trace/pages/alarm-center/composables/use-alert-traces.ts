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

import { type MaybeRef, reactive, shallowRef, watchEffect } from 'vue';

import { get } from '@vueuse/core';
import { alertTraces } from 'monitor-api/modules/alert_v2';

import { ExploreTableLoadingEnum } from '@/pages/trace-explore/components/trace-explore-table/typing';

import type { ALertTracesData, ALertTracesQueryConfig } from '../typings';

/**
 * @function useAlertTraces 调用链数据 hook
 * @description 告警详情 - 调用链 - 表格数据获取及相关的处理逻辑
 * @param {MaybeRef<string>} alertId 告警ID
 */
export const useAlertTraces = (alertId: MaybeRef<string>) => {
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

  /**
   * @method getTraceList 请求接口
   * @description 获取调用链表格数据
   */
  const getTraceList = async () => {
    if (!get(alertId)) return;
    if (pagination.offset === 0) {
      tableLoading[ExploreTableLoadingEnum.BODY_SKELETON] = true;
    } else {
      tableLoading[ExploreTableLoadingEnum.SCROLL] = true;
    }
    const data = await alertTraces<ALertTracesData>({
      alert_id: get(alertId),
      offset: pagination.offset,
      limit: pagination.limit,
    });
    if (pagination.offset === 0) {
      traceList.value = data.list;
      tableLoading[ExploreTableLoadingEnum.BODY_SKELETON] = false;
    } else {
      traceList.value = [...traceList.value, ...data.list];
      tableLoading[ExploreTableLoadingEnum.SCROLL] = false;
    }
    traceQueryConfig.value = data.query_config;
    tableHasMoreData.value = data.list?.length >= pagination.limit;
  };

  watchEffect(getTraceList);

  return {
    traceList,
    traceQueryConfig,
    tableLoading,
    pagination,
    tableHasMoreData,
  };
};
