/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 THL A29 Limited, a Tencent company.  All rights reserved.
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

import type { TapdTypeEnum, TAPDWorkspaceBoundEnum } from '../../constant';
import type { GetEnumTypeTool } from 'monitor-pc/pages/query-template/typings/constants';

export interface CreateTapdDefaultSetting {
  tapd_type?: '' | TapdType;
  workspace_id?: string;
}

/**
 * 创建 TAPD 单据响应 data
 * POST /fta/issue/issue/create_tapd/
 */
export interface CreateTapdIssueData {
  activities: IssueActivityItem[];
  bk_biz_id: number;
  description: string;
  issue_id: string;
  iteration_id: string;
  name: string;
  owner: string;
  priority_label: string;
  sync_status: boolean;
  tapd_id: string;
  tapd_type: TapdType;
  te?: string;
  workspace_id: number;
}

/**
 * 创建 TAPD 单据请求参数
 */
export interface CreateTapdIssueRequest {
  bk_biz_id: number;
  description: string;
  issue_id: string;
  iteration_id: string;
  name: string;
  owner: string;
  priority_label: 'High' | 'Low' | 'Middle' | 'Nice To Have';
  sync_status: boolean;
  tapd_type: TapdType;
  te?: string;
  workspace_id: number | string;
}

/** Issue 活动日志项 */
export interface IssueActivityItem {
  activity_id: string;
  activity_type: string;
  bk_biz_id: number;
  content: null | string;
  from_value: null | string;
  operator: string;
  time: number;
  to_value: null | string;
}

/** TAPD 列表项 */
export interface ITapdListItem {
  tapd_id: string;
  tapd_title: string;
  tapd_type: string;
}

/** Tapd单据类型 */
export type TapdType = GetEnumTypeTool<typeof TapdTypeEnum>;

/** TAPD工作空间绑定类型 */
export type TAPDWorkspaceBoundType = GetEnumTypeTool<typeof TAPDWorkspaceBoundEnum>;

/** TAPD 项目信息 */
export interface TapdWorkspaceItem {
  is_bound: TAPDWorkspaceBoundType;
  workspace_id: string;
  workspace_name: string;
}
