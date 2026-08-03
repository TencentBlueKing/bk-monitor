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

import { computed, onScopeDispose, shallowRef, watch } from 'vue';
import type { Ref, ShallowRef } from 'vue';

import { storeToRefs } from 'pinia';

import { useHostStore } from '../../../store/modules/host';
import { getHostProcessList } from '../services/process-service';

import type { ProcessItem } from '../types/process';
import type { IHostTopoHostNode } from '../types/topo';

/** 支持前端排序的数值列 key */
const SORTABLE_KEYS = new Set<keyof ProcessItem>(['cpuUsage', 'memRss', 'instanceCount', 'fdNum']);

/**
 * @description 进程列表业务编排：按选中主机加载数据，并在前端完成关键字搜索与排序。
 * 视图层（host-process / process-table）只消费这里暴露的状态与方法，保证 MVC 分层。
 */
export const useProcessList = (options: {
  host: Ref<IHostTopoHostNode | null>;
  keyword: ShallowRef<string>;
  /**
   * @description 数据加载完成后的回调函数（可选）
   * 用于在进程列表加载完成后执行额外逻辑，如自动选中某个进程
   * @param list - 加载完成的进程列表数据
   */
  loadDataEnd?: (list: ProcessItem[]) => void;
}) => {
  const { timeRangeTimestamp } = storeToRefs(useHostStore());
  const { keyword } = options;
  const loading = shallowRef(false);
  /** 原始进程数据（接口原样数据） */
  const rawList = shallowRef<ProcessItem[]>([]);
  /** 排序（`-key` 倒序 / `key` 正序） */
  const sortInfo = shallowRef('');
  /** 当前请求的 AbortController，用于取消未完成的请求 */
  let abortController: AbortController | null = null;

  const loadData = async () => {
    // 取消上一次未完成的请求，避免快速切换主机时竞态
    abortController?.abort();
    const host = options.host.value;
    if (!host) {
      rawList.value = [];
      return;
    }

    const controller = new AbortController();
    abortController = controller;
    const { signal } = controller;

    loading.value = true;
    const data = await getHostProcessList(
      {
        bk_target_ip: host.ip,
        bk_target_cloud_id: String(host.bk_cloud_id ?? ''),
        start_time: timeRangeTimestamp.value.start_time,
        end_time: timeRangeTimestamp.value.end_time,
      },
      { signal }
    );
    // 请求被取消（主机切换 / 组件卸载），丢弃本次结果
    if (signal.aborted) return;
    rawList.value = data;
    loading.value = false;
    /** 触发数据加载完成回调（如有），用于外部处理加载后逻辑 */
    options?.loadDataEnd?.(data);
  };

  /** 关键字过滤：命中进程名 */
  const filteredList = computed<ProcessItem[]>(() => {
    const kw = keyword.value.trim().toLowerCase();
    if (!kw) {
      return rawList.value;
    }
    return rawList.value.filter(item => item.name.toLowerCase().includes(kw));
  });

  /** 排序后的展示数据 */
  const displayList = computed<ProcessItem[]>(() => {
    if (!sortInfo.value) {
      return filteredList.value;
    }
    const descending = sortInfo.value.startsWith('-');
    const key = (descending ? sortInfo.value.slice(1) : sortInfo.value) as keyof ProcessItem;
    if (!SORTABLE_KEYS.has(key)) {
      return filteredList.value;
    }
    return [...filteredList.value].sort((a, b) => {
      const diff = Number(a[key]) - Number(b[key]);
      return descending ? -diff : diff;
    });
  });

  const handleKeywordChange = (value: string) => {
    keyword.value = value;
  };

  const handleSortChange = (value: string) => {
    sortInfo.value = value;
  };

  // 选中主机或时间范围变化时重新拉取
  watch([() => options.host.value, timeRangeTimestamp], () => loadData(), { immediate: true });

  // 组件卸载（effect scope 释放）时终止未完成的请求
  onScopeDispose(() => {
    abortController?.abort();
    abortController = null;
  });

  return {
    loading,
    sortInfo,
    displayList,
    loadData,
    handleKeywordChange,
    handleSortChange,
  };
};
