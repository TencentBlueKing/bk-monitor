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

import type { ShallowRef } from 'vue';

import { IssueStatusEnum } from '../alarm-issues/constant';

import type { IssueItem, IssuePriorityType } from '../alarm-issues/typing';

export interface UseIssuesOperationsOptions {
  /** 完整数据集的响应式引用（由 useIssuesTable 提供） */
  allData: ShallowRef<IssueItem[]>;
}

/**
 * @description Issues 业务操作 hook — 管理指派、标记解决、优先级变更等数据回写逻辑
 * @param options - 依赖选项，接收 useIssuesTable 提供的数据源
 * @returns 业务操作函数（handleAssign/handleMarkResolved/handlePriorityChange/handleShowDetail）
 */
export function useIssuesOperations({ allData }: UseIssuesOperationsOptions) {
  // ===================== 辅助函数 =====================

  // 更新指定 Issue 行的数据
  const updateIssueItem = (id: string, updates: Partial<IssueItem>) => {
    allData.value = allData.value.map(item => (item.id === id ? { ...item, ...updates } : item));
  };

  // ===================== 业务操作 =====================

  /**
   * @description 展示 Issue 详情
   * @param _id - Issue ID
   */
  const handleShowDetail = (_id: string) => {
    // TODO: 接入详情抽屉逻辑
  };

  /**
   * @description 指派负责人
   * @param id - Issue ID
   * @param assignee - 负责人列表
   */
  const handleAssign = (id: string, assignee: string[]) => {
    updateIssueItem(id, {
      assignee,
      ...(assignee.length > 0 ? { status: IssueStatusEnum.UNRESOLVED } : {}),
    });
  };

  /**
   * @description 标记已解决
   * @param id - Issue ID
   */
  const handleMarkResolved = (id: string) => {
    updateIssueItem(id, { status: IssueStatusEnum.RESOLVED });
  };

  /**
   * @description 优先级变更
   * @param id - Issue ID
   * @param priority - 新优先级
   */
  const handlePriorityChange = (id: string, priority: IssuePriorityType) => {
    updateIssueItem(id, { priority });
  };

  return {
    /** 展示详情 */
    handleShowDetail,
    /** 指派负责人 */
    handleAssign,
    /** 标记已解决 */
    handleMarkResolved,
    /** 优先级变更 */
    handlePriorityChange,
  };
}
