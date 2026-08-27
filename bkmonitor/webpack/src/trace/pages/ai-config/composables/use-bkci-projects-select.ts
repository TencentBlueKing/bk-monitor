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
import { shallowRef } from 'vue';

import { getBkciProjects } from '../services/ai-config';

import type { TBkciProjectsResult } from '../typings';

/** 每页加载数量 */
const PAGE_SIZE = 20;

/**
 * @description 蓝盾项目下拉选择数据加载逻辑（支持远程搜索 + 滚动加载）
 */
export function useBkciProjectsSelect() {
  /** 累积的项目选项列表 */
  const list = shallowRef<TBkciProjectsResult['list']>([]);
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
  /** 标记 Select 下拉面板是否处于展开状态，用于控制搜索时是否触发请求 */
  const isToggle = shallowRef(false);

  /**
   * @description 调用接口查询蓝盾项目列表
   */
  const fetchList = async (isLoadMore = false) => {
    // 已有请求在执行中则跳过，防止重复并发请求
    if (loading.value || scrollLoading.value) return;
    if (!isLoadMore) {
      loading.value = true;
      list.value = [];
      page.value = 1;
    } else {
      // 滚动加载更多时仅显示列表内部 loading
      scrollLoading.value = true;
    }

    try {
      const data = await getBkciProjects({
        keyword: keyword.value,
        page: page.value,
        page_size: PAGE_SIZE,
      });
      const items = data.list ?? [];
      list.value = isLoadMore ? [...list.value, ...items] : items;
      hasMore.value = items.length >= PAGE_SIZE;
    } finally {
      loading.value = false;
      scrollLoading.value = false;
    }
  };

  /** 初始加载 / 重置后重新加载 */
  const fetchData = () => fetchList(false);

  /** 搜索关键词变化：仅在下拉面板展开时触发请求，避免面板关闭时的无效搜索 */
  const handleSearch = (val: string) => {
    keyword.value = val;
    if (isToggle.value) {
      fetchList(false);
    }
  };

  /** Select 滚动到底部触发加载更多 */
  const handleScrollEnd = () => {
    if (!hasMore.value || scrollLoading.value) return;
    page.value += 1;
    fetchList(true);
  };

  /** Select 下拉面板展开/收起回调，展开时重新拉取最新数据 */
  const handleToggle = (val: boolean) => {
    isToggle.value = val;
    if (val) {
      fetchData();
    }
  };

  return {
    list,
    loading,
    scrollLoading,
    hasMore,
    isToggle,
    fetchData,
    handleSearch,
    handleScrollEnd,
    handleToggle,
  };
}
