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

import { type Ref, ref as deepRef, onMounted, onScopeDispose, shallowRef, watchEffect } from 'vue';

import { commonPageSizeGet } from 'monitor-common/utils';

import type { IssuesService } from '../../services/issues-services';
import type { CommonFilterParams } from '../../typings';
import type { IssueItem } from '../typing';

/** useIssuesTable 入参类型 */
interface UseIssuesTableOptions {
  /** 公共筛选参数（响应式） */
  filterParams: Ref<Partial<CommonFilterParams>>;
  /** IssuesService 实例 */
  service: IssuesService;
}

/**
 * @description Issues 表格数据管理 hook（与 store 解耦，依赖由调用方注入）
 * @param {UseIssuesTableOptions} options - service 实例与公共筛选参数
 * @returns {{ pageSize, page, total, data, loading, ordering }} 表格状态
 */
export function useIssuesTable(options: UseIssuesTableOptions) {
  const { service, filterParams } = options;
  /** 分页参数 */
  const pageSize = shallowRef(commonPageSizeGet() ?? 50);
  /** 当前页 */
  const page = shallowRef(1);
  /** 总条数 */
  const total = shallowRef(0);
  /** 表格数据（深响应式，支持直接修改行对象属性后触发重新渲染） */
  const data = deepRef<IssueItem[]>([]);
  /** 排序 */
  const ordering = shallowRef('');
  /** 是否加载中 */
  const loading = shallowRef(false);
  /** 请求中止控制器 */
  let abortController: AbortController | null = null;

  /**
   * @description 获取 Issues 表格数据的副作用函数
   * @returns {void}
   */
  const effectFunc = async () => {
    // 中止上一次未完成的请求
    if (abortController) {
      abortController.abort();
    }
    // 创建新的中止控制器
    abortController = new AbortController();
    const { signal } = abortController;

    loading.value = true;
    data.value = [];
    const res = await service.getFilterTableList<IssueItem>(
      {
        ...filterParams.value,
        page_size: pageSize.value,
        page: page.value,
        ordering: ordering.value ? [ordering.value] : [],
      },
      { signal }
    );
    // 检查请求是否已被中止，确保不会更新过期数据
    if (signal.aborted) return;
    total.value = res.total;
    data.value = res.data;
    loading.value = false;
  };

  onMounted(() => {
    watchEffect(effectFunc);
  });

  onScopeDispose(() => {
    // 中止未完成的请求
    if (abortController) {
      abortController.abort();
      abortController = null;
    }
    pageSize.value = commonPageSizeGet() ?? 50;
    page.value = 1;
    total.value = 0;
    data.value = [];
    loading.value = false;
    ordering.value = '';
  });

  return {
    pageSize,
    page,
    total,
    data,
    loading,
    ordering,
  };
}
