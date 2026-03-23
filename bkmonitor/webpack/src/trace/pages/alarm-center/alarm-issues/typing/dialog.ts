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

import type { IssuesBatchActionEnum } from '../constant';
import type { IssuePriorityType } from './constants';
import type { IssuesBatchActionType } from './constants';
import type { IssueItem } from './table';

/** 指派负责人请求参数 */
export interface AssignIssuesParams {
  /** 负责人用户名列表 */
  assignee: string[];
  /** 跨业务批量操作 Issue 标识列表 */
  issues: IssueIdentifier[];
}

export interface DialogEventByActionMap {
  [IssuesBatchActionEnum.ASSIGN]: IssuesAssigneeDialogEvent;
  [IssuesBatchActionEnum.FOLLOW_UP]: IssuesFollowUpDialogEvent;
  [IssuesBatchActionEnum.PRIORITY]: IssuesPriorityDialogEvent;
  [IssuesBatchActionEnum.RESOLVE]: IssuesResolveDialogEvent;
}

/** Issue 标识符（跨业务批量操作请求中的单条 issue 结构） */
export interface IssueIdentifier {
  /** 空间业务 ID */
  bk_biz_id: number;
  /** Issue ID */
  issue_id: string;
}

/** 指派责任人 dialog 组件 确认提交成功的回调事件对象 */
export interface IssuesAssigneeDialogEvent {
  assignee: IssueItem['assignee'];
  issue_id: IssueItem['id'];
  status: IssueItem['status'];
  update_time: IssueItem['update_time'];
}

/** 添加跟进信息 dialog 组件 确认提交成功的回调事件对象 */
export interface IssuesFollowUpDialogEvent {
  activity_id: string;
  activity_type: 'comment' | string;
  content: string;
  issue_id: IssueItem['id'];
  operator: string;
  time: null | number;
}

/** ISSUES 各操作 dialog 组件 回调事件对象 */
export interface IssuesOperationDialogEvent<U extends IssuesBatchActionType = IssuesBatchActionType> {
  failed: { issue_id: IssueItem['id']; message: string }[];
  succeeded: DialogEventByActionMap[U][];
}

/** ISSUES 各操作 dialog 组件所需的非公共私有参数(打开时需要回填显示的属性) */
export type IssuesOperationDialogParams = IssuesPriorityDialogParams;

/** 修改优先级 dialog 组件 确认提交成功的回调事件对象 */
export interface IssuesPriorityDialogEvent {
  issue_id: IssueItem['id'];
  priority: IssueItem['priority'];
  update_time: IssueItem['update_time'];
}

/** 修改优先级 dialog 组件所需私有参数 */
export interface IssuesPriorityDialogParams {
  /** 修改后的优先级（P0 P1 P2） */
  priority?: IssueItem['priority'];
}

/** 标记为已解决 dialog 组件 确认提交成功的回调事件对象 */
export interface IssuesResolveDialogEvent {
  issue_id: IssueItem['id'];
  resolved_time: IssueItem['resolved_time'];
  status: IssueItem['status'];
  update_time: IssueItem['update_time'];
}

/** 标记已解决请求参数 */
export interface ResolveIssuesParams {
  /** 跨业务批量操作 Issue 标识列表 */
  issues: IssueIdentifier[];
}

/** 修改优先级请求参数 */
export interface UpdatePriorityParams {
  /** 跨业务批量操作 Issue 标识列表 */
  issues: IssueIdentifier[];
  /** 目标优先级 */
  priority: IssuePriorityType;
}
