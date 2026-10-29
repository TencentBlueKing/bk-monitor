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

/**
 * @description 当前操作人的蓝盾项目候选项，展开选择器时加载
 */
export function useBkciProjectsSelect() {
  /** 项目选项列表 */
  const list = shallowRef<TBkciProjectsResult['list']>([]);
  /** 加载态 */
  const loading = shallowRef(false);
  /** id -> 名称 的映射表，供外部按 id 反查展示名称（如详情回显） */
  const nameMap = shallowRef<Map<string, string>>(new Map());
  let loaded = false;
  let pending: null | Promise<boolean> = null;

  /**
   * @description 调用接口查询蓝盾项目全量列表
   */
  const fetchList = () => {
    // 空列表也是有效结果；仅成功后缓存，失败时允许下次展开重试。
    if (loaded) return Promise.resolve(true);
    if (pending) return pending;
    loading.value = true;

    pending = (async () => {
      try {
        const data = await getBkciProjects({});
        const items = data.list ?? [];
        const tempMap = new Map();
        for (const item of items) {
          tempMap.set(item.id, item.name);
        }
        nameMap.value = tempMap;
        list.value = items;
        loaded = true;
        return true;
      } catch {
        // 接口错误由全局拦截器提示，这里只恢复可重试状态。
        return false;
      }
    })().finally(() => {
      loading.value = false;
      pending = null;
    });
    return pending;
  };

  return {
    list,
    loading,
    nameMap,
    fetchList,
  };
}
