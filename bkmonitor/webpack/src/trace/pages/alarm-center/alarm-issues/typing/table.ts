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

import type { IssuePriorityType, IssueStatusType, IssueTypeType } from './constants';

/** Issues 数据项 */
export interface IssueItem extends Record<string, unknown> {
  /** 告警事件数量 */
  alert_count: number;
  /** 负责人列表 */
  assignee: string[];
  /** 关键报错信息 */
  exception_type: string;
  /** 最早发生时间（时间戳，秒） */
  first_seen: number;
  /** Issue 唯一标识 */
  id: string;
  /** 影响主机数 */
  impact_host_count: number;
  /** 影响服务 */
  impact_service: string;
  /** Issue 名称（默认为告警策略名称） */
  issue_name: string;
  /** Issue 类型 */
  issue_type: IssueTypeType;
  /** 最后出现时间（时间戳，秒） */
  last_seen: number;
  /** 优先级 */
  priority: IssuePriorityType;
  /** 告警级别 */
  severity: number;
  /** 状态 */
  status: IssueStatusType;
  /** 标签列表 */
  tags: string[];
  /** 趋势数据 */
  trend_data: number[];
}
