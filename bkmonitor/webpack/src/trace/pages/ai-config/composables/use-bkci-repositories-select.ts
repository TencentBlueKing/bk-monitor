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

interface UseBkciRepositoriesSelectOptions {
  /** 蓝盾项目 id，为空时不加载仓库列表 */
  bkciProjectId: Ref<string>;
}

/**
 * @description 源码仓库下拉选择数据加载逻辑（依赖蓝盾项目，全量加载，切换项目时拉取一次）
 */
export function useBkciRepositoriesSelect(options: UseBkciRepositoriesSelectOptions) {
  const { bkciProjectId } = options;

  /** 仓库选项列表 */
  const list = shallowRef<TBkciRepositoriesResult['list']>([]);
  /** 加载态 */
  const loading = shallowRef(false);
  /** id -> 名称 的映射表，供外部按 id 反查展示名称（如详情回显） */
  const nameMap = shallowRef<Map<string, string>>(new Map());

  /**
   * @description 调用接口查询指定蓝盾项目下的源码仓库全量列表
   */
  const fetchList = async () => {
    // 前置校验：未选择蓝盾项目或已有请求在执行中则跳过
    if (!bkciProjectId.value || loading.value) return;
    loading.value = true;

    try {
      const data = await getBkciRepositories({
        bkci_project_id: bkciProjectId.value,
      });
      const items = data.list ?? [];
      // 填充 id -> 名称映射，供外部回显使用
      for (const item of items) {
        nameMap.value.set(item.id, item.name);
      }
      list.value = items;
    } finally {
      loading.value = false;
    }
  };

  /** 当蓝盾项目变化时，清空仓库列表并拉取新项目的全量仓库 */
  watch(
    bkciProjectId,
    () => {
      list.value = [];
      nameMap.value = new Map();
      fetchList();
    },
    { immediate: true }
  );

  /** 详情回显：拉取当前蓝盾项目下的全量仓库并填充映射表 */
  const fetchDataInit = () => fetchList();

  return {
    list,
    loading,
    nameMap,
    fetchDataInit,
  };
}
