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

import type { IssueActivityItem, TapdType } from '../../typing';
import type { TapdWorkspaceItem } from './index';

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

/**
 * 获取用户项目数据列表请求参数
 */
export interface GetUserWorkspaceData {
  install_url: string;
  items: TapdWorkspaceItem[];
  total: number;
}

/** 获取用户项目数据列表响应数据 */
export interface GetUserWorkspaceRequest {
  bk_biz_id: number | string;
  error_url: string;
  success_url: string;
}

/** 重新关联TAPD项目 */
export type RebindWorkspaceRequest = UnbindWorkspaceRequest;

/** 取消授权请求参数 */
export interface RevokeAuthRequest {
  bk_biz_id: number | string;
}

/**
 * 取消关联项目请求参数
 */
export interface UnbindWorkspaceRequest {
  bk_biz_id: number | string;
  workspace_id: number | string;
}
