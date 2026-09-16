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

import type { LlmInputObservation, LlmKvPair, LlmTextItem, LlmToolCallRecord, LlmToolDefinition } from './typings';

/** 输入消息原始结构（兼容 content / parts） */
type LlmMessage = {
  content?: unknown;
  parts?: unknown;
  role?: unknown;
};

/** 输入消息 part 原始结构 */
type LlmMessagePart = {
  arguments?: unknown;
  content?: unknown;
  id?: unknown;
  name?: unknown;
  response?: unknown;
  type?: unknown;
};

/**
 * @description 统计输入 Tab 各分区条目总数，用于页签角标
 */
export function countInputObservation(observation: LlmInputObservation): number {
  return (
    observation.userMessages.length +
    observation.modelMessages.length +
    observation.systemPrompts.length +
    observation.reasoningMessages.length +
    observation.toolCalls.length +
    observation.availableTools.length
  );
}

/**
 * @description 将对象拍成预览用 KV 列表，默认最多 4 项
 */
export function flattenKvPairs(value: unknown, max = 4): LlmKvPair[] {
  const parsed = parseJsonValue(value);
  if (!isRecord(parsed)) return [];
  return Object.entries(parsed)
    .slice(0, max)
    .map(([key, val]) => ({
      key,
      value:
        typeof val === 'string' || typeof val === 'number' || typeof val === 'boolean'
          ? String(val)
          : stringifyContent(val),
    }));
}

/**
 * @description 从 Span attributes 解析输入 Tab 观测数据
 */
export function parseInputObservation(attributes: Record<string, unknown>): LlmInputObservation {
  const messages = pickList(attributes, ['gen_ai.input.messages', 'gen_ai.prompt_messages']) as LlmMessage[];
  const systemInstructions = pickList(attributes, ['gen_ai.system_instructions']);
  const toolDefinitions = pickList(attributes, ['gen_ai.tool.definitions']);

  const userMessages: LlmTextItem[] = [];
  const modelMessages: LlmTextItem[] = [];
  const systemFromMessages: LlmTextItem[] = [];
  const reasoningMessages: LlmTextItem[] = [];
  const toolCallStore = new Map<string, LlmToolCallRecord>();
  let seq = 0;
  const nextId = (prefix: string) => `${prefix}-${++seq}`;

  for (const message of messages) {
    if (!isRecord(message)) continue;
    const role = String(message.role || '').toLowerCase();
    for (const part of toMessageParts(message)) {
      const type = String(part.type || 'text').toLowerCase();
      if (type === 'text') {
        const item = toTextItem(nextId(role || 'text'), part.content);
        if (!item) continue;
        if (role === 'user') userMessages.push(item);
        else if (role === 'assistant' || role === 'model') modelMessages.push(item);
        else if (role === 'system') systemFromMessages.push(item);
        continue;
      }
      if (type === 'reasoning') {
        const item = toTextItem(nextId('reasoning'), part.content);
        if (item) reasoningMessages.push(item);
        continue;
      }
      if (type === 'tool_call' || type === 'tool_call_response') {
        upsertToolCall(toolCallStore, part, nextId('tool'));
      }
    }
  }

  const systemPrompts = systemInstructions
    .map((item, index) => {
      if (typeof item === 'string') return toTextItem(`system-${index}`, item);
      if (!isRecord(item)) return null;
      const type = String(item.type || 'text').toLowerCase();
      if (type !== 'text') return null;
      return toTextItem(`system-${index}`, item.content);
    })
    .filter((item): item is LlmTextItem => Boolean(item));

  applyToolSpanAttributes(toolCallStore, attributes);

  return {
    userMessages,
    modelMessages,
    systemPrompts: systemPrompts.length ? systemPrompts : systemFromMessages,
    reasoningMessages,
    toolCalls: [...toolCallStore.values()],
    availableTools: toolDefinitions
      .map((item, index) => toToolDefinition(item, index))
      .filter((item): item is LlmToolDefinition => Boolean(item)),
  };
}

/** Tool Span 用 gen_ai.tool.call.* 补齐调用记录，不把 result 并入输入以免和输出重复 */
function applyToolSpanAttributes(store: Map<string, LlmToolCallRecord>, attributes: Record<string, unknown>): void {
  const id = String(getByPath(attributes, 'gen_ai.tool.call.id') || '').trim();
  const name = String(getByPath(attributes, 'gen_ai.tool.name') || '').trim();
  const argsValue = getByPath(attributes, 'gen_ai.tool.call.arguments');
  if (!id && !name && argsValue === undefined) return;

  const key = id || name || 'tool-span';
  const current = store.get(key) || { id: key, name: '', arguments: undefined, response: undefined };
  if (name && !current.name) current.name = name;
  if (argsValue !== undefined && current.arguments === undefined) {
    current.arguments = parseJsonValue(argsValue);
  }
  store.set(key, current);
}

/** 将消息拆成统一 part 列表 */
function toMessageParts(message: LlmMessage): LlmMessagePart[] {
  if (Array.isArray(message.parts)) {
    return message.parts.filter(item => isRecord(item)) as LlmMessagePart[];
  }
  if (message.content == null || message.content === '') return [];
  return [{ type: 'text', content: message.content }];
}

/** 将 tool.definitions 单项转成可用工具定义 */
function toToolDefinition(value: unknown, index: number): LlmToolDefinition | null {
  if (!isRecord(value)) return null;
  const name = String(value.name || '').trim();
  if (!name && value.description == null && value.parameters == null) return null;
  return {
    name: name || `tool-${index + 1}`,
    description: stringifyContent(value.description).trim(),
    parameters: parseJsonValue(value.parameters) ?? {},
  };
}

/** 按 id 合并 tool_call / tool_call_response，补齐 arguments 与 response */
function upsertToolCall(store: Map<string, LlmToolCallRecord>, part: LlmMessagePart, fallbackId: string): void {
  const id = String(part.id || fallbackId);
  const current = store.get(id) || { id, name: '', arguments: undefined, response: undefined };
  if (part.name) current.name = String(part.name);
  if (part.arguments !== undefined) current.arguments = parseJsonValue(part.arguments);
  if (part.response !== undefined) current.response = parseJsonValue(part.response);
  else if (part.content !== undefined && current.response === undefined) {
    current.response = parseJsonValue(part.content);
  }
  store.set(id, current);
}
