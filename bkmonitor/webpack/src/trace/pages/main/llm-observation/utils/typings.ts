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

/** LLM 观测页数据类型 */

/** list_llm_spans 返回的标准化 Span */
export type ILlmSpan = {
  attributes?: Record<string, unknown>;
  elapsed_time?: number;
  end_time?: number;
  parent_span_id?: string;
  resource?: Record<string, unknown>;
  span_id?: string;
  span_name?: string;
  start_time?: number;
  status?: {
    code?: number;
    message?: string;
  };
  trace_id?: string;
};

/** list_llm_spans 响应 data */
export type ILlmSpanListData = {
  spans?: ILlmSpan[];
  total?: number;
  trace_id?: string;
};

/** 输入 Tab 解析后的观测数据 */
export type LlmInputObservation = {
  /** 当前可用工具定义 */
  availableTools: LlmToolDefinition[];
  /** 模型/助手消息 */
  modelMessages: LlmTextItem[];
  /** 推理过程文本 */
  reasoningMessages: LlmTextItem[];
  /** 系统 Prompts */
  systemPrompts: LlmTextItem[];
  /** 已发生的工具调用记录 */
  toolCalls: LlmToolCallRecord[];
  /** 用户消息 */
  userMessages: LlmTextItem[];
};

/** 工具调用预览用的扁平 KV */
export type LlmKvPair = {
  key: string;
  value: string;
};

/** 按 gen_ai.operation.name 区分的观测页类型 */
export type LlmObservationKind = 'agent' | 'model' | 'tool';

/** 输出 Tab 解析后的观测数据 */
export type LlmOutputObservation = {
  /** 模型最终输出 */
  modelOutputs: LlmTextItem[];
  /** 规划中的工具调用 */
  plannedToolCalls: LlmPlannedToolCall[];
  /** 推理过程文本 */
  reasoningMessages: LlmTextItem[];
  /** 工具调用结果 */
  toolResults: LlmToolResult[];
};

/** 规划中的工具调用（输出侧） */
export type LlmPlannedToolCall = {
  arguments: unknown;
  description: string;
  id: string;
  name: string;
};

/** 统一文本条目（消息 / Prompt / 推理） */
export type LlmTextItem = {
  content: string;
  id: string;
};

/** 输入侧已发生的工具调用记录 */
export type LlmToolCallRecord = {
  arguments: unknown;
  id: string;
  name: string;
  response: unknown;
};

/** 可用工具定义 */
export type LlmToolDefinition = {
  description: string;
  name: string;
  parameters: unknown;
};

/** Tool Span 观测页数据 */
export type LlmToolObservation = {
  arguments: unknown;
  description: string;
  name: string;
  result: unknown;
};

/** 输出侧工具调用结果 */
export type LlmToolResult = {
  id: string;
  name: string;
  result: unknown;
};
