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
import { getByPath, isRecord, parseJsonValue, pickList, stringifyContent, toTextItem } from './helpers';

import type { LlmOutputObservation, LlmPlannedToolCall, LlmTextItem, LlmToolResult } from './typings';

/** 输出消息原始结构（兼容 content / parts / tool_calls） */
type LlmMessage = {
  content?: unknown;
  parts?: unknown;
  role?: unknown;
  tool_calls?: unknown;
};

/** 输出消息 part 原始结构 */
type LlmMessagePart = {
  arguments?: unknown;
  content?: unknown;
  description?: unknown;
  function?: unknown;
  id?: unknown;
  input?: unknown;
  name?: unknown;
  parameters?: unknown;
  text?: unknown;
  type?: unknown;
};

/**
 * @description 统计输出 Tab 各分区条目总数，用于页签角标
 */
export function countOutputObservation(observation: LlmOutputObservation): number {
  return (
    observation.reasoningMessages.length +
    observation.plannedToolCalls.length +
    observation.modelOutputs.length +
    observation.toolResults.length
  );
}

/**
 * @description 从 Span attributes 解析输出 Tab 观测数据
 */
export function parseOutputObservation(attributes: Record<string, unknown>): LlmOutputObservation {
  const messages = pickList(attributes, ['gen_ai.output.messages', 'gen_ai.completion_messages']);
  const toolDefinitions = pickList(attributes, ['gen_ai.tool.definitions']);
  const descriptionMap = toolDefinitions.reduce<Record<string, string>>((acc, item) => {
    if (!isRecord(item)) return acc;
    const name = String(item.name || '').trim();
    if (!name) return acc;
    acc[name] = stringifyContent(item.description).trim();
    return acc;
  }, {});

  const modelOutputs: LlmTextItem[] = [];
  const plannedToolCalls: LlmPlannedToolCall[] = [];
  const reasoningMessages: LlmTextItem[] = [];
  let seq = 0;
  const nextId = (prefix: string) => `${prefix}-${++seq}`;

  for (const message of messages) {
    if (typeof message === 'string') {
      const item = toTextItem(nextId('output'), message);
      if (item) modelOutputs.push(item);
      continue;
    }
    if (!isRecord(message)) continue;
    const role = String(message.role || '').toLowerCase();
    for (const part of toMessageParts(message)) {
      const type = String(
        part.type || (part.name || part.arguments !== undefined ? 'tool_call' : 'text')
      ).toLowerCase();
      if (type === 'reasoning') {
        const item = toTextItem(nextId('reasoning'), part.content ?? part.text);
        if (item) reasoningMessages.push(item);
        continue;
      }
      if (type === 'text') {
        if (role && role !== 'assistant' && role !== 'model') continue;
        const item = toTextItem(nextId('output'), part.content ?? part.text);
        if (item) modelOutputs.push(item);
        continue;
      }
      if (isToolCallType(type)) {
        const name = String(part.name || '').trim();
        plannedToolCalls.push({
          id: String(part.id || nextId('tool')),
          name,
          description: getToolDescription(descriptionMap, name, part),
          arguments: parseJsonValue(part.arguments) ?? {},
        });
      }
    }
  }

  return {
    modelOutputs,
    plannedToolCalls,
    reasoningMessages,
    toolResults: parseToolResults(attributes),
  };
}

/** 优先取 part 上的描述，否则回落到 tool.definitions */
function getToolDescription(definitions: Record<string, string>, name: string, part?: LlmMessagePart): string {
  const fromPart = stringifyContent(part?.description).trim();
  if (fromPart) return fromPart;
  return definitions[name] || '';
}

/** 兼容多种工具调用 part.type */
function isToolCallType(type: string): boolean {
  return ['function', 'function_call', 'functioncall', 'tool_call', 'tool_use'].includes(type);
}

/** 将 function / input / parameters 等别名归一到 name + arguments */
function normalizePart(value: unknown): LlmMessagePart | null {
  if (!isRecord(value)) return null;
  const fn = isRecord(value.function) ? value.function : null;
  return {
    ...value,
    name: value.name ?? fn?.name,
    arguments: value.arguments ?? value.input ?? value.parameters ?? fn?.arguments,
  };
}

/** 从 gen_ai.tool.call.result 解析输出侧工具结果 */
function parseToolResults(attributes: Record<string, unknown>): LlmToolResult[] {
  const result = getByPath(attributes, 'gen_ai.tool.call.result');
  if (result === undefined) return [];
  const id = String(getByPath(attributes, 'gen_ai.tool.call.id') || '').trim();
  const name = String(getByPath(attributes, 'gen_ai.tool.name') || '').trim();
  return [
    {
      id: id || name || 'tool-result',
      name,
      result: parseJsonValue(result),
    },
  ];
}

/** 将消息拆成统一 part 列表，必要时补齐独立的 tool_calls */
function toMessageParts(message: LlmMessage): LlmMessagePart[] {
  const parts: LlmMessagePart[] = [];
  if (Array.isArray(message.parts)) {
    parts.push(...message.parts.map(normalizePart).filter((item): item is LlmMessagePart => Boolean(item)));
  } else if (Array.isArray(message.content)) {
    parts.push(...message.content.map(normalizePart).filter((item): item is LlmMessagePart => Boolean(item)));
  } else if (message.content != null && message.content !== '') {
    parts.push({ type: 'text', content: message.content });
  }

  const hasToolCall = parts.some(part => isToolCallType(String(part.type || '').toLowerCase()));
  if (!hasToolCall && Array.isArray(message.tool_calls)) {
    parts.push(...message.tool_calls.map(normalizePart).filter((item): item is LlmMessagePart => Boolean(item)));
  }
  return parts;
}
