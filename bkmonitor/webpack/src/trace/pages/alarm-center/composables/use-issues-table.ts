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

import { generateMockIssues } from '../alarm-issues/issues-table/mock-data';

import type { IssueItem } from '../alarm-issues/typing';
import type { TablePagination } from '../typings';

/** 默认分页配置 */
const DEFAULT_PAGINATION: TablePagination = {
  currentPage: 1,
  pageSize: 10,
  total: 0,
};

/**
 * @description Issues 表格数据管理 hook（参考 useAlarmTable 设计模式）
 * @returns 表格状态（data/loading/pagination/sort/selectedRowKeys）及分页、排序、选中行的事件处理函数
 */
export function useIssuesTable() {
  // ===================== 数据状态 =====================

  /** 完整 mock 数据集（后续替换为 API 请求） */
  const allData = shallowRef<IssueItem[]>(generateMockIssues(198));

  /** 分页状态 */
  const pagination = shallowRef<TablePagination>({
    ...DEFAULT_PAGINATION,
    total: 198,
  });

  /** 排序状态 */
  const sort = shallowRef<string>('');

  /** 选中行 keys */
  const selectedRowKeys = shallowRef<string[]>([]);

  /** 加载状态 */
  const loading = shallowRef(false);

  // TODO: 接入真实 API 时，参考 useAlarmTable 添加 AbortController + watchEffect 模式
  // let abortController: AbortController | null = null;
  // onMounted(() => { watchEffect(effectFunc); });

  /** 当前页展示数据（模拟分页） */
  const tableData = computed(() => {
    const { currentPage, pageSize } = pagination.value;
    const start = (currentPage - 1) * pageSize;
    return allData.value.slice(start, start + pageSize);
  });

  // ===================== 事件处理 =====================

  /**
   * @description 页码变化回调
   * @param page - 当前页码
   */
  const handleCurrentPageChange = (page: number) => {
    pagination.value = { ...pagination.value, currentPage: page };
  };

  /**
   * @description 每页条数变化回调
   * @param pageSize - 每页条数
   */
  const handlePageSizeChange = (pageSize: number) => {
    pagination.value = { ...pagination.value, pageSize, currentPage: 1 };
  };

  /**
   * @description 排序变化回调
   * @param sortVal - 排序值
   */
  const handleSortChange = (sortVal: string | string[]) => {
    sort.value = Array.isArray(sortVal) ? sortVal[0] || '' : sortVal;
  };

  /**
   * @description 选中行变化回调
   * @param keys - 选中行 keys
   */
  const handleSelectionChange = (keys: string[]) => {
    selectedRowKeys.value = keys;
  };

  // ===================== 生命周期 =====================

  onScopeDispose(() => {
    pagination.value = { ...DEFAULT_PAGINATION };
    sort.value = '';
    selectedRowKeys.value = [];
    loading.value = false;
    allData.value = [];
  });

  return {
    /** 完整数据集（供业务操作 hook 读写） */
    allData,
    /** 当前页展示数据 */
    tableData,
    /** 分页状态 */
    pagination,
    /** 排序状态 */
    sort,
    /** 选中行 keys */
    selectedRowKeys,
    /** 加载状态 */
    loading,
    /** 页码变化处理 */
    handleCurrentPageChange,
    /** 每页条数变化处理 */
    handlePageSizeChange,
    /** 排序变化处理 */
    handleSortChange,
    /** 选中行变化处理 */
    handleSelectionChange,
  };
}
