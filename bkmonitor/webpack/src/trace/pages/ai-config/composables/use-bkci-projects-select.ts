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
 * @description 蓝盾项目下拉选择数据加载逻辑
 * 接口一次返回当前用户全部可访问的项目，不分页；搜索交由 Select 本地过滤。
 */
export function useBkciProjectsSelect() {
  /** 全量项目选项列表 */
  const list = shallowRef<TBkciProjectsResult['list']>([]);
  /** 加载态 */
  const loading = shallowRef(false);

  /**
   * @description 调用接口查询蓝盾项目列表
   */
  const fetchData = async () => {
    // 已有请求在执行中则跳过，防止重复并发请求
    if (loading.value) return;
    loading.value = true;
    try {
      const data = await getBkciProjects();
      list.value = data.list ?? [];
    } finally {
      loading.value = false;
    }
  };

  /** Select 下拉面板展开/收起回调，展开时重新拉取最新数据 */
  const handleToggle = (val: boolean) => {
    if (val) {
      fetchData();
    }
  };

  return {
    list,
    loading,
    fetchData,
    handleToggle,
  };
}
