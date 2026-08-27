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

import type { AiResourceOption, AiResourceResult } from '../typings';

/** 资源下拉查询 API 函数签名 */
type AiResourceApiFn = () => Promise<AiResourceResult>;

/**
 * @description 流程实例参数资源下拉选择数据加载逻辑
 * 通用工厂：传入不同的查询 API（智能体 / Skill / 知识库），复用同一套下拉数据加载策略。
 *
 * 接口一次返回当前用户全部可见资源，不分页：规则只保存资源 id，编辑态需要用 id 反查名称与
 * 所属空间做回填，分页会让已选资源落在未加载的页里而无法回填。搜索交由 Select 本地过滤。
 */
export function useAiResourceSelect(apiFn: AiResourceApiFn) {
  /** 全量选项列表 */
  const list = shallowRef<AiResourceOption[]>([]);
  /** 加载态 */
  const loading = shallowRef(false);
  /** 是否已加载过，避免每次展开下拉都重复请求全量数据 */
  const loaded = shallowRef(false);
  /** 当前请求的 AbortController，用于丢弃过期响应、避免竞态覆盖新数据 */
  let abortController: AbortController | null = null;

  /**
   * @description 拉取全量资源选项
   * 过期响应（被新请求 / 卸载取消）直接丢弃，不回写 list，避免数据竞态。
   */
  const fetchList = async () => {
    // 取消上一次未完成的请求，避免竞态导致旧响应覆盖新数据
    abortController?.abort();
    const controller = new AbortController();
    abortController = controller;
    const { signal } = controller;

    loading.value = true;
    try {
      const data = await apiFn();
      if (signal.aborted) return;
      list.value = data.list ?? [];
      loaded.value = true;
    } finally {
      // 仅当本次请求未被取消时才收尾 loading，避免误清空最新请求的加载态
      if (!signal.aborted) {
        loading.value = false;
      }
    }
  };

  /**
   * @description 确保选项已加载
   * 编辑态需要在弹窗打开时就拿到全量列表，才能用已保存的资源 id 回填名称与空间。
   */
  const ensureLoaded = () => (loaded.value || loading.value ? Promise.resolve() : fetchList());

  /**
   * @description Select 下拉面板展开/收起回调，展开时按需加载一次全量数据
   */
  const handleToggle = (val: boolean) => {
    if (val) {
      ensureLoaded();
    }
  };

  /**
   * @description 重置下拉状态，关闭弹窗时调用以清理残留数据；同时终止未完成的查询请求
   **/
  const reset = () => {
    abortController?.abort();
    abortController = null;
    list.value = [];
    loading.value = false;
    loaded.value = false;
  };

  onScopeDispose(() => {
    // 取消未完成的查询，避免组件卸载后过期响应回写状态
    abortController?.abort();
    abortController = null;
  });

  return {
    list,
    loading,
    ensureLoaded,
    handleToggle,
    reset,
  };
}
