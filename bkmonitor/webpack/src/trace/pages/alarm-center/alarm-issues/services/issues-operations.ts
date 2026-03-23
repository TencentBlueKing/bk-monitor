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

import { Message } from 'bkui-vue';

import { mockAssignIssues, mockResolveIssues, mockUpdatePriority } from '../issues-table/mock-data';

import type { RequestOptions } from '../../services/base';
import type {
  AssignIssuesParams,
  IssuesOperationDialogEvent,
  ResolveIssuesParams,
  UpdatePriorityParams,
} from '../typing';

/**
 * @description 指派 Issues 负责人，封装底层 API 调用、错误兜底与数据预处理
 * @param {AssignIssuesParams} params - 指派请求参数（issues / assignee）
 * @param {RequestOptions} options - 请求配置选项
 * @returns {Promise<IssuesOperationDialogEvent<'assign'>>} 包含 succeeded 和 failed 的操作结果；异常时返回空兜底结构
 */
export const assignIssues = async (
  params: AssignIssuesParams,
  options?: RequestOptions
): Promise<IssuesOperationDialogEvent<'assign'>> => {
  const data = await mockAssignIssues(params, options).catch(() => ({ succeeded: [], failed: [] }));
  return data;
};

/**
 * @description 修改 Issues 优先级，封装底层 API 调用、错误兜底与数据预处理
 * @param {UpdatePriorityParams} params - 修改优先级请求参数（issues / priority）
 * @param {RequestOptions} options - 请求配置选项
 * @returns {Promise<IssuesOperationDialogEvent<'priority'>>} 包含 succeeded 和 failed 的操作结果；异常时返回空兜底结构
 */
export const updateIssuesPriority = async (
  params: UpdatePriorityParams,
  options?: RequestOptions
): Promise<IssuesOperationDialogEvent<'priority'>> => {
  const data = await mockUpdatePriority(params, options).catch(() => ({ succeeded: [], failed: [] }));
  return data;
};

/**
 * @description 标记 Issues 为已解决，封装底层 API 调用、错误兜底与数据预处理
 * @param {ResolveIssuesParams} params - 标记已解决请求参数（issues）
 * @param {RequestOptions} options - 请求配置选项
 * @returns {Promise<IssuesOperationDialogEvent<'resolve'>>} 包含 succeeded 和 failed 的操作结果；异常时返回空兜底结构
 */
export const resolveIssues = async (
  params: ResolveIssuesParams,
  options?: RequestOptions
): Promise<IssuesOperationDialogEvent<'resolve'>> => {
  const data = await mockResolveIssues(params, options).catch(() => ({ succeeded: [], failed: [] }));
  return data;
};

/**
 * @description 统一处理 Issues 操作结果的 Message 提示：根据 failed 列表判断成功/失败并弹出对应提示
 * @param {IssuesOperationDialogEvent} res - 操作结果（包含 succeeded 和 failed）
 * @param {string} successMessage - 操作成功时的提示文案
 * @returns {void}
 */
export const showOperationResult = (res: IssuesOperationDialogEvent, successMessage: string): void => {
  const hasFailed = !!res.failed?.length;
  Message({
    theme: hasFailed ? 'error' : 'success',
    message: hasFailed ? res.failed[0]?.message : successMessage,
  });
};
