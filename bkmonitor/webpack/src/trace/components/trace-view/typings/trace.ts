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

export type CrossRelation = {
  app_name: string;
  bk_app_code: number;
  bk_biz_id: number;
  bk_biz_name: string;
  permission: boolean;
  trace_id: string;
};

export type GroupInfo = {
  duration: number;
  id: string;
  members: string[];
};

export type KeyValuePair = {
  key: string;
  value: any;
};

export type Link = {
  text: string;
  url: string;
};

export type Log = {
  fields: Array<KeyValuePair>;
  timestamp: number;
};

export type Process = {
  serviceName: string;
  tags: Array<KeyValuePair>;
};

export type Span = SpanData & {
  depth: number;
  hasChildren: boolean;
  process: Process;
  references: NonNullable<SpanData['references']>;
  relativeStartTime: number;
  subsidiarilyReferencedBy: Array<SpanReference>;
  tags: NonNullable<SpanData['tags']>;
  warnings: NonNullable<SpanData['warnings']>;
};

export type SpanAttributesItem = {
  key: string;
  query_key: string;
  query_value: string;
  type: string;
  value: string;
};

export type SpanData = {
  app_name: string;
  attributes?: Array<SpanAttributesItem>;
  bgColor?: string;
  color?: string;
  cross_relation: CrossRelation;
  duration: number;
  ebpf_kind: string; // ebpf 类型
  ebpf_tap_port_name?: string;
  ebpf_tap_side?: string;
  ebpf_thread_name?: string;
  error?: boolean;
  group_info: GroupInfo; // 折叠分组信息
  icon?: string;
  is_expand: boolean; // 折叠节点当前被展开
  is_virtual: boolean; // 是否推断（虚拟）span
  kind?: number;
  logs: Array<Log>;
  mark?: string;
  operationName: string;
  processID: string;
  references?: Array<SpanReference>;
  service_name: string;
  source?: string;
  span_id: string;
  spanID: string;
  startTime: number;
  tags?: Array<KeyValuePair>;
  traceID: string;
  warnings?: Array<string> | null;
};

export type SpanReference = {
  refType: 'CHILD_OF' | 'FOLLOWS_FROM';

  span: null | Span | undefined;
  spanID: string;
  traceID: string;
};

export type TNil = tNil;

export type Trace = TraceData & {
  duration: number;
  endTime: number;
  services: { name: string; numberOfSpans: number }[];
  spans: Span[];
  startTime: number;
  traceName: string;
};

export type TraceData = {
  processes: Record<string, Process>;
  traceID: string;
};
