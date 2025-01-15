/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition):
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

import type tNil from './TNil';

export type TNil = tNil;

export type KeyValuePair = {
  key: string;
  value: any;
};

export type Link = {
  url: string;
  text: string;
};

export type Log = {
  timestamp: number;
  fields: Array<KeyValuePair>;
};

export type Process = {
  serviceName: string;
  tags: Array<KeyValuePair>;
};

export type SpanReference = {
  refType: 'CHILD_OF' | 'FOLLOWS_FROM';

  span: Span | null | undefined;
  spanID: string;
  traceID: string;
};

export type CrossRelation = {
  app_name: string;
  bk_app_code: number;
  bk_biz_id: number;
  bk_biz_name: string;
  trace_id: string;
  permission: boolean;
};

export type GroupInfo = {
  id: string;
  members: string[];
  duration: number;
};

export type SpanData = {
  span_id: string;
  spanID: string;
  traceID: string;
  processID: string;
  operationName: string;
  app_name: string;
  startTime: number;
  duration: number;
  logs: Array<Log>;
  tags?: Array<KeyValuePair>;
  references?: Array<SpanReference>;
  warnings?: Array<string> | null;
  error?: boolean;
  icon?: string;
  service_name: string;
  color?: string;
  cross_relation: CrossRelation;
  kind?: number;
  source?: string;
  is_virtual: boolean; // 是否推断（虚拟）span
  ebpf_kind: string; // ebpf 类型
  ebpf_thread_name?: string;
  ebpf_tap_side?: string;
  ebpf_tap_port_name?: string;
  group_info: GroupInfo; // 折叠分组信息
  is_expand: boolean; // 折叠节点当前被展开
  mark?: string;
  bgColor?: string;
};

export type Span = SpanData & {
  depth: number;
  hasChildren: boolean;
  process: Process;
  relativeStartTime: number;
  tags: NonNullable<SpanData['tags']>;
  references: NonNullable<SpanData['references']>;
  warnings: NonNullable<SpanData['warnings']>;
  subsidiarilyReferencedBy: Array<SpanReference>;
};

export type TraceData = {
  processes: Record<string, Process>;
  traceID: string;
};

export type Trace = TraceData & {
  duration: number;
  endTime: number;
  spans: Span[];
  startTime: number;
  traceName: string;
  services: { name: string; numberOfSpans: number }[];
};
