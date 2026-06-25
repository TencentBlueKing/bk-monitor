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

import type { TapdType, TAPDWorkspaceBoundType } from './constants';

export interface CreateTapdDefaultSetting {
  tapd_type?: '' | TapdType;
  workspace_id?: string;
}

/**
 * 创建 TAPD 单据响应 data
 * POST /fta/issue/issue/create_tapd/
 */
export interface CreateTapdIssueData {
  /** 该 Issue 全部活动日志，按发生时间降序排列（最新在前） */
  activities: IssueActivityItem[];
  /** 业务 ID */
  bk_biz_id: number;
  /** TAPD 单据详细描述 */
  description: string;
  /** Issue ID */
  issue_id: string;
  /** 迭代 ID */
  iteration_id: string;
  /** TAPD 单据标题 */
  name: string;
  /** TAPD 单据处理人 */
  owner: string;
  /** TAPD 单据优先级 */
  priority_label: string;
  /** 是否同步单据状态 */
  sync_status: boolean;
  /** 创建的 TAPD 单据 ID */
  tapd_id: string;
  /** TAPD 单据类型 */
  tapd_type: TapdType;
  /** 测试人员，bug 单据才返回这个字段 */
  te?: string;
  /** TAPD 项目 ID */
  workspace_id: number;
}

/**
 * 创建 TAPD 单据请求参数
 * POST /fta/issue/issue/create_tapd/
 */
export interface CreateTapdIssueRequest {
  /** 业务 ID */
  bk_biz_id: number;
  /** 详细描述 */
  description: string;
  /** 目标 Issue ID */
  issue_id: string;
  /** 迭代 ID */
  iteration_id: string;
  /** 单据标题 */
  name: string;
  /** 单据处理人，支持多成员（如：aaa;bbb;） */
  owner: string;
  /** 优先级，可选值: High（高）、Middle（中）、Low（低）、Nice To Have（无关紧要） */
  priority_label: 'High' | 'Low' | 'Middle' | 'Nice To Have';
  /** 是否同步单据状态 */
  sync_status: boolean;
  /** TAPD 单据类型，可选值：story（需求）、bug（缺陷） */
  tapd_type: TapdType;
  /** 测试人员，创建 bug 时必填 */
  te?: string;
  /** TAPD 项目 ID */
  workspace_id: number | string;
}

/**
 * Issue 活动日志项
 */
export interface IssueActivityItem {
  /** 活动记录 ID */
  activity_id: string;
  /** 活动类型（create_tapd、comment、assignee_change 等） */
  activity_type: string;
  /** 活动归属业务 ID */
  bk_biz_id: number;
  /** 内容字段（create_tapd 类型存储 JSON 格式的结构化内容） */
  content: null | string;
  /** 变更前的值 */
  from_value: null | string;
  /** 操作人 */
  operator: string;
  /** 活动发生时间（Unix 秒级时间戳） */
  time: number;
  /** 变更后的值 */
  to_value: null | string;
}

/**
 * TAPD 项目信息
 */
export interface TapdWorkspaceItem {
  is_bound: TAPDWorkspaceBoundType;
  workspace_id: string;
  workspace_name: string;
}
