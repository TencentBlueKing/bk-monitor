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

import type { IssueActiveNodeTypeEnum, IssuePriorityEnum, IssueStatusEnum, IssueTypeEnum } from '../constant';
import type { GetEnumTypeTool } from 'monitor-pc/pages/query-template/typings/constants';

/** Issues 活跃节点类型 */
export type IssueActiveNodeType = GetEnumTypeTool<typeof IssueActiveNodeTypeEnum>;

/** Issues 优先级类型 */
export type IssuePriorityType = GetEnumTypeTool<typeof IssuePriorityEnum>;

/** Issues 状态类型 */
export type IssueStatusType = GetEnumTypeTool<typeof IssueStatusEnum>;

/** Issues 类型 */
export type IssueTypeType = GetEnumTypeTool<typeof IssueTypeEnum>;

// ===================== 接口定义 =====================

/** 映射条目通用结构 */
export interface MapEntry {
  /** 显示别名 */
  alias: string;
  /** 背景颜色值 */
  bgColor?: string;
  /** 颜色值 */
  color: string;
  /** 图标类名 */
  icon?: string;
}
