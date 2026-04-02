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

import { request } from 'monitor-api/base';

import type { RequestOptions } from '../../services/base';
import type { CommonFilterParams } from '../../typings';
import type {
  AssignIssuesParams,
  FollowUpIssuesParams,
  IssueItem,
  IssuesOperationDialogEvent,
  ResolveIssuesParams,
  UpdatePriorityParams,
} from '../typing';

export const searchIssue = request('POST', '/fta/issue/issue/search/');
export const assignIssue = request('POST', '/fta/issue/issue/assign/');
export const resolveIssue = request('POST', '/fta/issue/issue/resolve/');
export const reopenIssue = request('POST', '/fta/issue/issue/reopen/');
export const archiveIssue = request('POST', '/fta/issue/issue/archive/');
export const restoreIssue = request('POST', '/fta/issue/issue/restore/');
export const updatePriority = request('POST', '/fta/issue/issue/update_priority/');
export const addFollowUp = request('POST', '/fta/issue/issue/add_follow_up/');

/** mock 请求参数类型 */
type MockFetchParams = CommonFilterParams & {
  show_aggs?: boolean;
  show_dsl?: boolean;
};
/**
 * @description 模拟请求 Issues 列表接口，支持分页与排序（含网络延迟模拟）
 * @param {MockFetchParams} params - 请求参数（page / page_size / ordering）
 * @returns {Promise<{ total: number; data: IssueItem[] }>} 分页后的响应结构
 */
export const fetchMockIssues = async (
  params: Partial<MockFetchParams>,
  config: RequestOptions
): Promise<{ aggs: any; issues: IssueItem[]; total: number }> => {
  return await searchIssue(params, config);
};

/**
 * @description 模拟指派负责人接口
 * @param {AssignIssuesParams} params - 指派请求参数（issues / assignee）
 * @param {RequestOptions} config - 请求配置选项
 * @returns {Promise<IssuesOperationDialogEvent<'assign'>>} 包含 succeeded 和 failed 的操作结果
 */
export const mockAssignIssues = async (
  params: AssignIssuesParams,
  config?: RequestOptions
): Promise<IssuesOperationDialogEvent<'assign'>> => {
  return await assignIssue(params, config);
};

/**
 * @description 模拟修改优先级接口，更新 mock 数据缓存中的 Issue 优先级并返回操作结果
 * @param {UpdatePriorityParams} params - 修改优先级请求参数（issues / priority）
 * @param {RequestOptions} config - 请求配置选项
 * @returns {Promise<IssuesOperationDialogEvent<'priority'>>} 包含 succeeded 和 failed 的操作结果
 */
export const mockUpdatePriority = async (
  params: UpdatePriorityParams,
  config?: RequestOptions
): Promise<IssuesOperationDialogEvent<'priority'>> => {
  return await updatePriority(params, config);
};

/**
 * @description 模拟标记已解决接口
 * @param {ResolveIssuesParams} params - 请求参数（issues）
 * @param {RequestOptions} config - 请求配置选项
 * @returns {Promise<IssuesOperationDialogEvent<'resolve'>>} 包含 succeeded 和 failed 的操作结果
 */
export const mockResolveIssues = async (
  params: ResolveIssuesParams,
  config?: RequestOptions
): Promise<IssuesOperationDialogEvent<'resolve'>> => {
  return await resolveIssue(params, config);
};
/**
 * @description 模拟重新打开接口
 * @param {ResolveIssuesParams} params - 请求参数（issues）
 * @param {RequestOptions} config - 请求配置选项
 * @returns {Promise<IssuesOperationDialogEvent<'resolve'>>} 包含 succeeded 和 failed 的操作结果
 */
export const mockReopenIssues = async (
  params: ResolveIssuesParams,
  config?: RequestOptions
): Promise<IssuesOperationDialogEvent<'resolve'>> => {
  return await reopenIssue(params, config);
};

/**
 * @description 模拟归档接口
 * @param {ResolveIssuesParams} params - 请求参数（issues）
 * @param {RequestOptions} config - 请求配置选项
 * @returns {Promise<IssuesOperationDialogEvent<'resolve'>>} 包含 succeeded 和 failed 的操作结果
 */
export const mockArchiveIssues = async (
  params: ResolveIssuesParams,
  config?: RequestOptions
): Promise<IssuesOperationDialogEvent<'resolve'>> => {
  return await archiveIssue(params, config);
};

/**
 * @description 模拟恢复归档接口
 * @param {ResolveIssuesParams} params - 请求参数（issues）
 * @param {RequestOptions} config - 请求配置选项
 * @returns {Promise<IssuesOperationDialogEvent<'resolve'>>} 包含 succeeded 和 failed 的操作结果
 */
export const mockRestoreIssues = async (
  params: ResolveIssuesParams,
  config?: RequestOptions
): Promise<IssuesOperationDialogEvent<'resolve'>> => {
  return await restoreIssue(params, config);
};

/**
 * @description 模拟添加跟进信息接口，为指定 Issue 生成跟进记录并返回操作结果
 * @param {FollowUpIssuesParams} params - 添加跟进信息请求参数（issues / content）
 * @param {RequestOptions} config - 请求配置选项
 * @returns {Promise<IssuesOperationDialogEvent<'follow_up'>>} 包含 succeeded 和 failed 的操作结果
 */
export const mockFollowUpIssues = async (
  params: FollowUpIssuesParams,
  config?: RequestOptions
): Promise<IssuesOperationDialogEvent<'follow_up'>> => {
  return await addFollowUp(params, config);
};
