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
import { type MaybeRef, computed, shallowRef, watch } from 'vue';

import { get } from '@vueuse/core';
import { random } from 'monitor-common/utils';

import { handleTransformToTimestamp } from '../../../components/time-range/utils';
import { useRumExploreStore } from '../../../store/modules/rum-explore';
import { RUM_TABLE_PAGE_LIMIT } from '../constants';
import { getRecordList } from '../services/rum-search';

import type { IRumCommonParams, IRumSpanRecord } from '../typings';

/**
 * @description RUM 检索表格数据管理。查询条件、排序、时间范围或手动刷新变化时重新拉第一页；触底时按 offset 追加。用自增的 requestId 丢弃过期响应，避免快速切换条件时旧结果覆盖新结果。
 * @param {MaybeRef<IRumCommonParams>} commonParams 检索公共请求参数（应用名、查询语句等）
 */
export function useRumTableData(commonParams: MaybeRef<IRumCommonParams>) {
  const store = useRumExploreStore();

  /** 表格记录列表 */
  const tableData = shallowRef<IRumSpanRecord[]>([]);
  /** 首次加载 / 条件变化时的整表 loading */
  const loading = shallowRef(false);
  /** 触底追加时的 loading */
  const scrollLoading = shallowRef(false);
  /** 是否还有下一页数据 */
  const hasMore = shallowRef(false);
  /** 回到顶部信号。查询条件、排序、时间范围或手动刷新变化时重新生成随机串，由外层视图组件监听并触发滚动复位；使用信号而非回调，避免父组件通过 ref 直接调用子组件方法，保持数据流单向 */
  const backTopSignal = shallowRef(random(8));
  /** 排序参数（与接口一致，降序加 `-` 前缀，如 '-end_time'）。由 store 派生：用户未设置排序时回落视图配置的默认排序，对外只读，变更统一走 handleSortChange */
  const sortParams = computed(() => store.sortParams);
  /** 请求序号，用于丢弃过期响应 */
  let requestId = 0;

  /**
   * @description 拉取表格数据。无 app_name 时清空列表；响应返回后若已有更新的请求则丢弃本次结果
   * @param {boolean} isLoadMore 是否为触底加载更多（true 按当前列表长度作为 offset 追加，false 重新拉第一页）
   */
  async function fetchList(isLoadMore = false) {
    if (!get(commonParams).app_name) {
      tableData.value = [];
      hasMore.value = false;
      return;
    }
    requestId += 1;
    const currentRequestId = requestId;
    if (isLoadMore) {
      scrollLoading.value = true;
    } else {
      loading.value = true;
    }

    const [startTime, endTime] = handleTransformToTimestamp(store.timeRange);
    const offset = isLoadMore ? tableData.value.length : 0;
    const list = await getRecordList({
      ...get(commonParams),
      start_time: startTime,
      end_time: endTime,
      offset,
      limit: RUM_TABLE_PAGE_LIMIT,
      sort: sortParams.value,
    });

    // 期间又发起了新请求，丢弃本次结果
    if (currentRequestId !== requestId) return;

    tableData.value = isLoadMore ? [...tableData.value, ...list] : list;
    hasMore.value = list.length >= RUM_TABLE_PAGE_LIMIT;
    loading.value = false;
    scrollLoading.value = false;
  }

  /**
   * @description 表格触底回调。加载中或无更多数据时忽略，否则追加下一页
   */
  function handleScrollToEnd() {
    if (loading.value || scrollLoading.value || !hasMore.value) return;
    fetchList(true);
  }

  /**
   * @description 排序变化回调。CommonTable 的 sortChange 为单条字符串或数组（取消排序时为空串），归一化为接口的 sort 数组
   * @param {string | string[]} sort 排序字段（如 'field' 升序、'-field' 降序）
   */
  function handleSortChange(sort: string | string[]) {
    store.userSort = (Array.isArray(sort) ? sort : [sort]).filter(Boolean);
  }

  watch(
    () => [get(commonParams), sortParams.value, store.timeRange, store.refreshImmediate],
    () => {
      // 触发回到顶部信号，由外层 RumExploreView 监听并滚动到顶部
      backTopSignal.value = random(8);
      fetchList();
    },
    { immediate: true }
  );

  return {
    tableData,
    loading,
    scrollLoading,
    hasMore,
    sortParams,
    backTopSignal,
    fetchList,
    handleScrollToEnd,
    handleSortChange,
  };
}
