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

import { computed, onScopeDispose, shallowRef } from 'vue';

import { debounce } from 'lodash';

import type { AiResourceOption, AiResourceResult } from '../typings';

/** 资源下拉查询 API 函数签名（全量接口，无分页参数） */
type AiResourceApiFn = () => Promise<AiResourceResult>;

/** 搜索骨架屏时长（仅用于交互反馈，本地过滤本身即时完成） */
const SEARCH_LOADING_MS = 400;
/** 搜索防抖时长，避免逐字符触发过滤与骨架屏抖动 */
const SEARCH_DEBOUNCE_MS = 300;

/**
 * @description AI 资源下拉（智能体 / 知识库 / Skill 通用）composable
 * 接口返回全量数据，取消分页与远程搜索：侧弹打开时由父组件调用 fetchList 拉取一次，
 * 搜索由父组件监听 search-change 在本地对全量列表过滤（匹配 name / id）。
 * 选中值由父组件通过 modelValue 管控。
 */
export function useAiResourceSelect(apiFn: AiResourceApiFn) {
  /** 资源下拉全量列表 */
  const list = shallowRef<AiResourceOption[]>([]);
  /** 是否正在加载（首屏全量拉取） */
  const loading = shallowRef(false);
  /** 搜索关键词（外部本地过滤用） */
  const keyword = shallowRef('');
  /** 搜索中（展示下拉骨架屏的短暂态） */
  const searchLoading = shallowRef(false);
  const nameMap = shallowRef<Map<string, string>>(new Map());
  /** 竞态防护：取消上一轮未完成的请求，避免快速开关时旧响应覆盖新数据 */
  let abortControllerRef = new AbortController();
  /** 搜索骨架屏定时器 */
  let searchTimer: null | ReturnType<typeof setTimeout> = null;

  /** 拉取全量列表（侧弹打开时调用一次） */
  const fetchList = async () => {
    if (loading.value) return;
    abortControllerRef.abort();
    const curAbort = new AbortController();
    abortControllerRef = curAbort;
    loading.value = true;
    try {
      const res = await apiFn();
      if (!curAbort.signal.aborted) {
        list.value = res.list || [];
        const tempMap = new Map();
        for (const item of list.value) {
          tempMap.set(item.id, item.name);
        }
        nameMap.value = tempMap;
      }
    } catch {
      if (!curAbort.signal.aborted) {
        list.value = [];
      }
    } finally {
      if (!curAbort.signal.aborted) {
        loading.value = false;
      }
    }
  };

  /** 按关键词本地过滤全量列表（匹配 name / id，忽略大小写） */
  const filteredList = computed(() => {
    const kw = keyword.value.trim().toLowerCase();
    if (!kw) return list.value;
    return list.value.filter(item =>
      [item.id, item.name].filter(Boolean).some(v => String(v).toLowerCase().includes(kw))
    );
  });

  /** 搜索变更（防抖）：仅本地过滤全量列表，并触发短暂骨架屏用于交互反馈 */
  const handleSearch = debounce((val: string) => {
    keyword.value = val;
    searchLoading.value = true;
    if (searchTimer) clearTimeout(searchTimer);
    searchTimer = setTimeout(() => {
      searchLoading.value = false;
    }, SEARCH_LOADING_MS);
  }, SEARCH_DEBOUNCE_MS);

  /** 释放外部副作用（终止请求 / 取消防抖 / 清定时器），卸载与重置共用 */
  const clearSideEffects = () => {
    abortControllerRef.abort();
    handleSearch.cancel();
    if (searchTimer) clearTimeout(searchTimer);
  };

  /** 清空资源下拉残留状态（列表 / 加载态 / 搜索态），避免下次打开时显示旧数据 */
  const reset = () => {
    clearSideEffects();
    list.value = [];
    keyword.value = '';
    loading.value = false;
    searchLoading.value = false;
  };

  onScopeDispose(clearSideEffects);

  return {
    list,
    loading,
    searchLoading,
    filteredList,
    fetchList,
    handleSearch,
    reset,
    nameMap,
  };
}
