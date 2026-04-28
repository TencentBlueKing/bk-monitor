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

import type { IssuesBatchActionEnum } from '../constant';
import type { IssueActiveNodeType, IssuePriorityType, IssuesBatchActionType } from './constants';
import type { IssueItem } from './table';

// ===================== 请求参数类型 =====================

/** 指派负责人请求参数 */
export interface AssignIssuesParams {
  /** 负责人用户名列表 */
  assignee: IssueItem['assignee'];
  /** 跨业务批量操作 Issue 标识列表 */
  issues: IssueIdentifier[];
}

/** 指派负责人 - 成功条目 */
export interface AssignSucceededItem extends IssueOperationSucceededBase {
  /** 指派后的负责人用户名列表 */
  assignee: IssueItem['assignee'];
}

/** 添加跟进信息请求参数 */
export interface FollowUpIssuesParams {
  /** 跟进内容（markdown 格式） */
  content: string;
  /** 跨业务批量操作 Issue 标识列表 */
  issues: IssueIdentifier[];
}

/** Issue 活动记录条目 */
export interface IssueActivityItem {
  /** 活动记录 ID */
  activity_id: string;
  /** 活动类型 */
  activity_type: IssueActiveNodeType;
  /** 业务 ID */
  bk_biz_id: number;
  /** 评论内容（仅 comment 类型有值） */
  content: null | string;
  /** 变更前的值（仅 *_change 类型有值） */
  from_value: null | string;
  /** 操作人 */
  operator: string;
  /** 活动时间（Unix 秒级时间戳） */
  time: number;
  /** 变更后的值（仅 *_change 类型有值） */
  to_value: null | string;
}

/** Issue 标识符（跨业务批量操作请求中的单条 issue 结构） */
export interface IssueIdentifier {
  /** 该 Issue 所属的业务 ID */
  bk_biz_id: IssueItem['bk_biz_id'];
  /** Issue ID */
  issue_id: IssueItem['id'];
}

// ===================== 响应结构类型 =====================

/** 批量操作失败条目 */
export interface IssueOperationFailedItem {
  /** 该 Issue 所属的业务 ID */
  bk_biz_id: IssueItem['bk_biz_id'];
  /** Issue ID */
  issue_id: IssueItem['id'];
  /** 失败原因描述 */
  message: string;
}

/** 批量操作成功条目 - 公共字段 */
export interface IssueOperationSucceededBase {
  /** 该 Issue 的所有活动记录信息 */
  activities: IssueActivityItem[];
  /** 该 Issue 所属的业务 ID */
  bk_biz_id: IssueItem['bk_biz_id'];
  /** Issue ID */
  issue_id: IssueItem['id'];
  /** 操作后的 Issue 状态 */
  status: IssueItem['status'];
  /** 更新时间（Unix 秒级时间戳） */
  update_time: IssueItem['update_time'];
}

/** Issues 批量操作响应 */
export interface IssuesBatchOperationResponse<U extends IssuesBatchActionType = IssuesBatchActionType> {
  /** 失败的条目列表，含失败原因 */
  failed: IssueOperationFailedItem[];
  /** 成功处理的条目列表 */
  succeeded: IssueSucceededItemByActionMap[U][];
}

/** ISSUES 各操作 dialog 组件所需的非公共私有参数(打开时需要回填显示的属性) */
export type IssuesOperationDialogParams = IssuesPriorityDialogParams;

/** 修改优先级 dialog 组件所需私有参数 */
export interface IssuesPriorityDialogParams {
  /** 修改后的优先级（P0 P1 P2） */
  priority?: IssuePriorityType;
}

/** 批量操作响应 - 各操作类型的 succeeded 条目类型映射 */
export interface IssueSucceededItemByActionMap {
  [IssuesBatchActionEnum.ARCHIVE]: StatusChangeSucceededItem;
  [IssuesBatchActionEnum.ASSIGN]: AssignSucceededItem;
  [IssuesBatchActionEnum.FOLLOW_UP]: StatusChangeSucceededItem;
  [IssuesBatchActionEnum.PRIORITY]: UpdatePrioritySucceededItem;
  [IssuesBatchActionEnum.RESOLVE]: ResolveSucceededItem;
  [IssuesBatchActionEnum.UNARCHIVE]: StatusChangeSucceededItem;
  [IssuesBatchActionEnum.UNRESOLVE]: StatusChangeSucceededItem;
}

/** 标记已解决请求参数 */
export interface ResolveIssuesParams {
  /** 跨业务批量操作 Issue 标识列表 */
  issues: IssueIdentifier[];
}

// ===================== Dialog 专属类型 =====================

/** 标记已解决 - 成功条目 */
export interface ResolveSucceededItem extends IssueOperationSucceededBase {
  /** 解决时间 */
  resolved_time: IssueItem['resolved_time'];
}

/** 状态变更类操作 - 成功条目 */
export type StatusChangeSucceededItem = IssueOperationSucceededBase;

/** 修改优先级请求参数 */
export interface UpdatePriorityParams {
  /** 跨业务批量操作 Issue 标识列表 */
  issues: IssueIdentifier[];
  /** 目标优先级 */
  priority: IssuePriorityType;
}

/** 修改优先级 - 成功条目 */
export interface UpdatePrioritySucceededItem extends IssueOperationSucceededBase {
  /** 修改后的优先级 */
  priority: IssueItem['priority'];
}
