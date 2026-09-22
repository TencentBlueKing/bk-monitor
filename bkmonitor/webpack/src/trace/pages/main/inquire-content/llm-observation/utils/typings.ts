/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
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

import type { LlmKvPair } from '../../../llm-observation/utils/typings';

/**
 * Trace 详情 LLM 观测模块的类型定义。
 * 接口形态对齐 list_llm_flows；视图模型由 utils/transform 从 LlmFlowSpan 树派生。
 */

/** Agent 执行线类型筛选 */
export type LlmExecutionFilter = 'agent' | 'all' | 'error' | 'llm' | 'tool';

/**
 * 页面节点类型，由 attributes.gen_ai.operation.name 归类。
 * 未命中 Agent / 模型 / Tool 时不归类，按通用 GenAI Span 展示。
 */
export type LlmSpanKind = 'AGENT' | 'LLM' | 'TOOL';

/** list_llm_flows 树节点，字段与 list_llm_spans 的 spans 元素一致，childs 为直接子 Span */
export interface LlmFlowSpan {
  attributes?: Record<string, unknown>;
  childs?: LlmFlowSpan[];
  elapsed_time: number;
  end_time: number;
  parent_span_id?: string;
  resource?: Record<string, unknown>;
  span_id: string;
  span_name: string;
  start_time: number;
  status?: {
    code?: number;
    message?: string;
  };
  trace_id: string;
}

/** list_llm_flows traces 元素 */
export interface LlmFlowTrace {
  cache_read_input_tokens?: number;
  cache_write_input_tokens?: number;
  conversation_id?: string;
  elapsed_time?: number;
  end_time?: number;
  /** 会话模式下可能仅有摘要，完整 Span 树需按 trace_id 二次 listFlows */
  flow: LlmFlowSpan[];
  group_field?: string;
  group_id?: string;
  /** Trace 级用户输入 / 最终输出摘要，供 Trace 标题 Popover */
  input?: string;
  input_tokens?: number;
  output?: string;
  output_tokens?: number;
  start_time?: number;
  status?: string;
  total_tokens?: number;
  trace_id: string;
  user_id?: string;
}

/** list_llm_flows data */
export interface LlmFlowsResponse {
  cache_read_input_tokens?: number;
  cache_write_input_tokens?: number;
  elapsed_time?: number;
  end_time?: number;
  group_field?: string;
  group_id?: string;
  input_tokens?: number;
  output_tokens?: number;
  start_time?: number;
  total_tokens?: number;
  traces: LlmFlowTrace[];
}

/** 会话 / 单 Trace 概览汇总，供统计卡使用 */
export type LlmOverviewStats = Pick<
  LlmFlowsResponse,
  | 'cache_read_input_tokens'
  | 'cache_write_input_tokens'
  | 'elapsed_time'
  | 'input_tokens'
  | 'output_tokens'
  | 'total_tokens'
>;

/** 输入 → 输出预览：纯文本或可解析的 KV */
export type LlmIoPreview =
  | {
      input: LlmKvPair[];
      output: LlmKvPair[];
      type: 'kv';
    }
  | {
      input: string;
      output: string;
      type: 'text';
    };

/** 统计卡片 */
export interface LlmStatCard {
  key: string;
  label: string;
  theme?: 'success';
  unit?: string;
  value: string;
}

/** 扁平化后的 Span 行 */
export interface LlmSpanRowView {
  attributes: Record<string, unknown>;
  childCount: number;
  depth: number;
  /** Agent / 工具描述，模型行通常为空 */
  description: string;
  elapsedTime: number;
  /** status.message，status.code === 2 时用于错误 icon tooltip */
  errorMessage: string;
  hasChildren: boolean;
  inputTokens: number;
  io: LlmIoPreview;
  isError: boolean;
  isLast: boolean;
  /** 关系列竖线层级：根下子节点为 0，嵌套 Agent 展开后的子级递增 */
  lineGuideLevel: number;
  kind?: LlmSpanKind;
  name: string;
  outputTokens: number;
  /** 原始 Span JSON（不含子节点） */
  rawSpan: Record<string, unknown>;
  spanId: string;
  startTime: number;
  subtitle: string;
  traceId: string;
}

/** Trace 分组视图 */
export interface LlmTraceView {
  conversationId: string;
  elapsedTime: number;
  errorCount: number;
  /** 该 Trace 的 flow 已按 trace_id 拉回 */
  flowLoaded: boolean;
  input: string;
  inputTokens: number;
  isCurrent: boolean;
  output: string;
  outputTokens: number;
  spanCount: number;
  startTime: number;
  title: string;
  totalTokens: number;
  traceId: string;
  userId: string;
}
