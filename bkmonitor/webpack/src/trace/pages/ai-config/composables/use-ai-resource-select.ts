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
import { onScopeDispose, shallowRef } from 'vue';

import { debounce } from 'lodash';

import type { AiResourceOption, AiResourceParams, AiResourceResult } from '../typings';

/** 每页加载数量 */
const PAGE_SIZE = 20;

/** 资源下拉查询 API 函数签名 */
type AiResourceApiFn = (params: AiResourceParams) => Promise<AiResourceResult>;

/**
 * @description 流程实例参数资源下拉选择数据加载逻辑（支持远程搜索 + 滚动加载）
 * 通用工厂：传入不同的查询 API（智能体 / Skill / 知识库），复用同一套下拉数据加载策略。
 */
export function useAiResourceSelect(apiFn: AiResourceApiFn) {
  /** 累积的选项列表 */
  const list = shallowRef<AiResourceOption[]>([]);
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
  /** 当前请求的 AbortController，用于丢弃过期响应、避免竞态覆盖新数据 */
  let abortController: AbortController | null = null;

  /**
   * @description 调用接口查询资源选项列表
   * 每次发起新请求前取消上一次未完成的请求；过期响应（被新请求/卸载取消）直接丢弃，
   * 不回写 list，从而避免快速连续触发（展开下拉后立即搜索等）时的数据竞态。
   */
  const fetchList = async (isLoadMore = false) => {
    // 取消上一次未完成的请求，避免竞态导致旧响应覆盖新数据
    abortController?.abort();
    const controller = new AbortController();
    abortController = controller;
    const { signal } = controller;

    if (!isLoadMore) {
      loading.value = true;
      list.value = [];
      page.value = 1;
    } else {
      // 滚动加载更多时仅显示列表内部 loading
      scrollLoading.value = true;
    }

    try {
      const data = await apiFn({ keyword: keyword.value, page: page.value, page_size: PAGE_SIZE });
      // 请求已被取消（新请求发起 / 组件卸载），丢弃本次结果；loading 交由最新请求收尾，避免闪烁
      if (signal.aborted) return;
      const items = data.list ?? [];
      list.value = isLoadMore ? [...list.value, ...items] : items;
      hasMore.value = items.length >= PAGE_SIZE;
    } finally {
      // 仅当本次请求未被取消时才收尾 loading，避免误清空最新请求的加载态
      if (!signal.aborted) {
        loading.value = false;
        scrollLoading.value = false;
      }
    }
  };
  const debouncedFetch = debounce(() => fetchList(false), 300);

  /**
   * @description 搜索关键词变化：仅在下拉面板展开时触发请求，避免面板关闭时的无效搜索
   */
  const handleSearch = (val: string) => {
    keyword.value = val;
    if (isToggle.value) {
      debouncedFetch();
    }
  };

  /**
   * @description 下拉列表滚动到底部时加载下一页
   * 无更多数据或正在加载中时跳过，避免重复请求。
   */
  const handleScrollEnd = () => {
    if (!hasMore.value || scrollLoading.value) return;
    page.value += 1;
    fetchList(true);
  };

  /**
   * @description Select 下拉面板展开/收起回调
   * 展开时重置条件并重新拉取最新数据；收起时仅更新展开状态标记。
   */
  const handleToggle = (val: boolean) => {
    isToggle.value = val;
    if (val) {
      fetchList(false);
    }
  };

  /**
   * @description 重置下拉状态，关闭弹窗时调用以清理残留数据；同时终止未完成的查询请求
   **/
  const reset = () => {
    // 取消未完成的查询与防抖搜索，避免关闭弹窗后过期响应回写状态
    debouncedFetch.cancel();
    abortController?.abort();
    abortController = null;
    list.value = [];
    loading.value = false;
    scrollLoading.value = false;
    hasMore.value = true;
    page.value = 1;
    keyword.value = '';
    isToggle.value = false;
  };

  onScopeDispose(() => {
    debouncedFetch.cancel();
    // 取消未完成的查询，避免组件卸载后过期响应回写状态
    abortController?.abort();
    abortController = null;
  });

  return {
    list,
    loading,
    scrollLoading,
    hasMore,
    isToggle,
    handleSearch,
    handleScrollEnd,
    handleToggle,
    reset,
  };
}
