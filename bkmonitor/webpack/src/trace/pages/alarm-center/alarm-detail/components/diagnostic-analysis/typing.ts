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

import type { DiagnosticTypeEnum } from './constant';
import type { GetEnumTypeTool } from 'monitor-pc/pages/query-template/typings/constants';
export type DiagnosticTypeEnumType = GetEnumTypeTool<typeof DiagnosticTypeEnum>;

/** 告警关联的故障摘要（alert_incident_detail） */
export interface IAlertIncidentBrief {
  bk_biz_id?: number;
  bk_biz_name?: string;
  id?: string;
  incident_id?: number;
  incident_name?: string;
}

/** BKFara 事件分析中的流程执行记录 */
export interface IBkFaraProcessItem {
  executeResult: string;
  executeTime: string;
  /** 流程详情跳转地址，联调前可为占位 */
  link?: string;
  name: string;
}

/** 内容项 */
export interface IContentItem {
  title: string;
  value: string[];
}

/** 表格项 */
export interface ITableItem {
  link?: boolean;
  name: string;
  value: string;
}

/** Pattern / 示例日志 内容块 */
export interface IPatternBlock {
  kind?: 'json' | 'text';
  title: string;
  value: string;
}
