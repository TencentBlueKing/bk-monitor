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
 * documentation files (the "Software"), to deal in the Software without restriction, including without limitation the
 * rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
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
import {
  addIssueFollowUp,
  archiveIssue,
  assignIssue,
  reopenIssue,
  resolveIssue,
  restoreIssue,
  updateIssuePriority,
} from 'monitor-api/modules/issue';

import type { RequestOptions } from '../../services/base';
import type {
  AssignIssuesParams,
  FollowUpIssuesParams,
  IssueIdentifier,
  IssuesBatchOperationResponse,
  ResolveIssuesParams,
  UpdatePriorityParams,
} from '../typing';

/**
 * @description 指派 Issues 负责人，封装底层 API 调用与数据预处理
 * @param {AssignIssuesParams} params - 指派请求参数（issues / assignee）
 * @param {RequestOptions} options - 请求配置选项
 * @returns {Promise<IssuesBatchOperationResponse<'assign'>>} 包含 succeeded 和 failed 的操作结果
 */
export const assignIssues = async (
  params: AssignIssuesParams,
  options?: RequestOptions
): Promise<IssuesBatchOperationResponse<'assign'>> => {
  const data = await assignIssue(params, options).catch(() => ({ succeeded: [], failed: [] }));
  return data;
};

/**
 * @description 修改 Issues 优先级，封装底层 API 调用与数据预处理
 * @param {UpdatePriorityParams} params - 修改优先级请求参数（issues / priority）
 * @param {RequestOptions} options - 请求配置选项
 * @returns {Promise<IssuesBatchOperationResponse<'priority'>>} 包含 succeeded 和 failed 的操作结果
 */
export const updateIssuesPriority = async (
  params: UpdatePriorityParams,
  options?: RequestOptions
): Promise<IssuesBatchOperationResponse<'priority'>> => {
  const data = await updateIssuePriority(params, options).catch(() => ({ succeeded: [], failed: [] }));
  return data;
};

/**
 * @description 标记 Issues 为已解决，封装底层 API 调用与数据预处理
 * @param {ResolveIssuesParams} params - 标记已解决请求参数（issues）
 * @param {RequestOptions} options - 请求配置选项
 * @returns {Promise<IssuesBatchOperationResponse<'resolve'>>} 包含 succeeded 和 failed 的操作结果
 */
export const resolveIssues = async (
  params: ResolveIssuesParams,
  options?: RequestOptions
): Promise<IssuesBatchOperationResponse<'resolve'>> => {
  const data = await resolveIssue(params, options).catch(() => ({ succeeded: [], failed: [] }));
  return data;
};

/**
 * @description 重新打开 Issues，封装底层 API 调用与数据预处理
 * @param {ResolveIssuesParams} params - 重新打开请求参数（issues）
 * @param {RequestOptions} options - 请求配置选项
 * @returns {Promise<IssuesBatchOperationResponse<'unresolve'>>} 包含 succeeded 和 failed 的操作结果
 */
export const unResolveIssues = async (
  params: ResolveIssuesParams,
  options?: RequestOptions
): Promise<IssuesBatchOperationResponse<'unresolve'>> => {
  const data = await reopenIssue(params, options).catch(() => ({ succeeded: [], failed: [] }));
  return data;
};

/**
 * @description 归档 Issues，封装底层 API 调用与数据预处理
 * @param {ResolveIssuesParams} params - 归档请求参数（issues）
 * @param {RequestOptions} options - 请求配置选项
 * @returns {Promise<IssuesBatchOperationResponse<'archive'>>} 包含 succeeded 和 failed 的操作结果
 */
export const archiveIssues = async (
  params: ResolveIssuesParams,
  options?: RequestOptions
): Promise<IssuesBatchOperationResponse<'archive'>> => {
  const data = await archiveIssue(params, options).catch(() => ({ succeeded: [], failed: [] }));
  return data;
};

/**
 * @description 恢复归档 Issues，封装底层 API 调用与数据预处理
 * @param {ResolveIssuesParams} params - 恢复归档请求参数（issues）
 * @param {RequestOptions} options - 请求配置选项
 * @returns {Promise<IssuesBatchOperationResponse<'unarchive'>>} 包含 succeeded 和 failed 的操作结果
 */
export const unArchiveIssues = async (
  params: ResolveIssuesParams,
  options?: RequestOptions
): Promise<IssuesBatchOperationResponse<'unarchive'>> => {
  const data = await restoreIssue(params, options).catch(() => ({ succeeded: [], failed: [] }));
  return data;
};

/**
 * @description 添加 Issues 跟进信息，封装底层 API 调用与数据预处理
 * @param {FollowUpIssuesParams} params - 添加跟进信息请求参数（issues / content）
 * @param {RequestOptions} options - 请求配置选项
 * @returns {Promise<IssuesBatchOperationResponse<'follow_up'>>} 包含 succeeded 和 failed 的操作结果
 */
export const followUpIssues = async (
  params: FollowUpIssuesParams,
  options?: RequestOptions
): Promise<IssuesBatchOperationResponse<'follow_up'>> => {
  const data = await addIssueFollowUp(params, options).catch(() => ({ succeeded: [], failed: [] }));
  return data;
};

/**
 * @description 导出 Issues 列表，封装底层 API 调用（当前为 mock 占位，待后端接口就绪后替换）
 * @param {IssueIdentifier[]} issues - 跨业务批量操作 Issue 标识列表
 * @param {RequestOptions} options - 请求配置选项
 * @returns {Promise<void>}
 */
export const exportIssues = async (issues: IssueIdentifier[], options?: RequestOptions): Promise<void> => {
  console.log('exportIssues', issues, options);
  // TODO: 替换为真实 API 调用，如 exportIssueList({ issues }, options)
  await new Promise(resolve => setTimeout(resolve, 1500));
};

/**
 * @description 统一处理 Issues 操作结果的 Message 提示：根据 succeeded / failed 列表判断成功/失败并弹出对应提示；
 *   当 succeeded 和 failed 均为空时不弹出任何提示（防御性兜底）
 * @param {IssuesBatchOperationResponse} res - 操作结果（包含 succeeded 和 failed）
 * @param {string} successMessage - 操作成功时的提示文案
 * @returns {boolean} 操作是否成功（true = 全部成功，false = 存在失败项或结果为空）
 */
export const showOperationResult = (res: IssuesBatchOperationResponse, successMessage: string): boolean => {
  const hasFailed = !!res.failed?.length;
  const hasSucceeded = !!res.succeeded?.length;
  if (hasFailed) {
    Message({ theme: 'error', message: res.failed[0]?.message });
    return false;
  }
  if (hasSucceeded) {
    Message({ theme: 'success', message: successMessage });
    return true;
  }
  return false;
};
