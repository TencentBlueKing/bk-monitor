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
import { type Ref, shallowRef, watch } from 'vue';

import { getBkciRepositories } from '../services/ai-config';

import type { TBkciRepositoriesResult } from '../typings';

/** 每页加载数量 */
const PAGE_SIZE = 20;

interface UseBkciRepositoriesSelectOptions {
  /** 蓝盾项目 id，为空时不加载仓库列表 */
  bkciProjectId: Ref<string>;
}

/**
 * @description 源码仓库下拉选择数据加载逻辑（依赖蓝盾项目，支持远程搜索 + 滚动加载）
 */
export function useBkciRepositoriesSelect(options: UseBkciRepositoriesSelectOptions) {
  const { bkciProjectId } = options;

  /** 累积的仓库选项列表 */
  const list = shallowRef<TBkciRepositoriesResult['list']>([]);
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
  /** id -> 名称 的映射表，供外部按 id 反查展示名称（如详情回显） */
  const nameMap = shallowRef<Map<string, string>>(new Map());

  /** 当蓝盾项目变化时，重置并清空仓库列表 */
  watch(
    bkciProjectId,
    () => {
      list.value = [];
      page.value = 1;
      hasMore.value = true;
      keyword.value = '';
    },
    { immediate: true }
  );

  /**
   * @description 调用接口查询指定蓝盾项目下的源码仓库列表
   */
  const fetchList = async (isLoadMore = false, id = '') => {
    // 前置校验：未选择蓝盾项目或已有请求在执行中则跳过
    if (!bkciProjectId.value || loading.value || scrollLoading.value) return;
    if (!isLoadMore) {
      loading.value = true;
      page.value = 1;
    } else {
      // 滚动加载更多时仅显示列表内部 loading
      scrollLoading.value = true;
    }

    try {
      const data = await getBkciRepositories({
        bkci_project_id: bkciProjectId.value,
        // keyword 为空时使用 id 回查（详情回显场景）：以 id 作为关键词定位目标项
        keyword: keyword.value || id,
        page: page.value,
        page_size: PAGE_SIZE,
      });
      const items = data.list ?? [];
      // 填充 id -> 名称映射，供外部回显使用
      for (const item of items) {
        nameMap.value.set(item.id, item.name);
      }
      list.value = isLoadMore ? [...list.value, ...items] : items;
      hasMore.value = items.length >= PAGE_SIZE;
    } finally {
      loading.value = false;
      scrollLoading.value = false;
    }
  };

  /** 初始加载 / 重置后重新加载 */
  const fetchData = () => fetchList(false);

  /** 详情回显：以给定 id 作为关键词回查列表，定位并加载目标仓库（不清空原有结果） */
  const fetchDataInit = (id = '') => fetchList(false, id);

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
    nameMap,
    fetchData,
    handleSearch,
    handleScrollEnd,
    handleToggle,
    fetchDataInit,
  };
}
