/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台 (BlueKing PaaS):
 *
 * ---------------------------------------------------
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
 * documentation files (the "Software"), to deal in the Software without restriction, including without limitation
 * the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
 * and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
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

import { type Ref, shallowRef } from 'vue';

import { searchTapdItemsApi } from '../services/tapd';

import type { ITapdListItem, TTapdStatus } from '../typing';

/** 每页加载数量 */
const PAGE_SIZE = 30;

interface UseTapdSelectOptions {
  bizId: Ref<number | string>;
  tapdType: Ref<string>;
  workspaceId: Ref<number | string>;
}

/** TODO: 临时 mock 数据，接口联调后删除 */
const MOCK_TOTAL = 52;
const MOCK_STATUSES: TTapdStatus[] = ['planning', 'developing', 'status_1', 'for_test', 'resolved'];
const MOCK_PRIORITIES = ['1', '2', '3'];

export function useTapdSelect(options: UseTapdSelectOptions) {
  const { bizId, workspaceId, tapdType } = options;

  /** 累积的选项列表 */
  const list = shallowRef<ITapdListItem[]>([]);
  /** 首次/搜索中加载态 */
  const loading = shallowRef(false);
  /** 滚动加载中 */
  const scrollLoading = shallowRef(false);
  /** 是否还有更多数据 */
  const hasMore = shallowRef(true);
  /** 当前页码 */
  const page = shallowRef(1);
  /** 当前搜索关键词 */
  const keyword = shallowRef('');

  /**
   * @description 调用接口查询 TAPD 单据列表
   */
  const fetchList = async (isLoadMore = false) => {
    if (!workspaceId.value || !bizId.value || !tapdType.value) return;
    if (!isLoadMore) {
      loading.value = true;
      list.value = [];
      page.value = 1;
    }
    scrollLoading.value = true;

    try {
      const data = await searchTapdItemsApi({
        bk_biz_id: Number(bizId.value),
        workspace_id: Number(workspaceId.value),
        tapd_type: tapdType.value,
        name: keyword.value || undefined,
        limit: PAGE_SIZE,
        page: page.value,
        fields: 'status',
      }).catch(() => null);
      let items = data ?? [];
      // TODO: 临时 mock，接口联调后删除此分支
      if (items.length === 0) {
        items = buildMockData(page.value, PAGE_SIZE, keyword.value || undefined);
      }
      list.value = isLoadMore ? [...list.value, ...items] : items;
      hasMore.value = items.length >= PAGE_SIZE;
    } catch (e) {
      console.error('searchTapdItems error:', e);
    } finally {
      loading.value = false;
      scrollLoading.value = false;
    }
  };

  /** 初始加载 / 重置后重新加载 */
  const fetchData = () => fetchList(false);

  /** 搜索关键词变化：重置分页并重新请求 */
  const handleSearch = (val: string) => {
    keyword.value = val;
    fetchList(false);
  };

  /** Select 滚动到底部触发加载更多 */
  const handleScrollEnd = () => {
    if (!hasMore.value || scrollLoading.value) return;
    page.value += 1;
    fetchList(true);
  };

  return {
    list,
    loading,
    scrollLoading,
    hasMore,
    fetchData,
    handleSearch,
    handleScrollEnd,
  };
}

function buildMockData(page: number, pageSize: number, keyword?: string): ITapdListItem[] {
  const list: ITapdListItem[] = [];
  const start = (page - 1) * pageSize;
  for (let i = start; i < Math.min(start + pageSize, MOCK_TOTAL); i++) {
    const name = `[Mock] TAPD 单据 ${i + 1} - ${['告警关联优化', 'TAPD 同步异常', '单据状态流转', '工单自动创建', '数据对接调试'][i % 5]}`;
    if (keyword && !name.toLowerCase().includes(keyword.toLowerCase())) continue;
    list.push({
      id: String(1000000 + i),
      name,
      status: MOCK_STATUSES[i % MOCK_STATUSES.length],
      priority: MOCK_PRIORITIES[i % MOCK_PRIORITIES.length],
      tapd_type: 'story',
      bk_biz_id: 0,
      workspace_id: 1000000000000,
      created: '2025-06-26 10:00:00',
    });
  }
  return list;
}
