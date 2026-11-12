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
import { isRecord, parseJsonValue, pickList, stringifyContent, toTextItem } from './helpers';

import type {
  LlmModelTimeline,
  LlmTextItem,
  LlmTimelineMessage,
  LlmTimelinePart,
  LlmTimelineRole,
  LlmToolDefinition,
} from './typings';

/** 输入 / 输出消息原始结构，按 parts 顺序展开 */
type LlmMessage = {
  content?: unknown;
  parts?: unknown;
  role?: unknown;
  tool_call_id?: unknown;
  tool_calls?: unknown;
};

/** 消息 part 原始结构 */
type LlmMessagePart = {
  arguments?: unknown;
  content?: unknown;
  description?: unknown;
  function?: unknown;
  id?: unknown;
  input?: unknown;
  name?: unknown;
  parameters?: unknown;
  response?: unknown;
  span_id?: unknown;
  spanId?: unknown;
  text?: unknown;
  tool_call_id?: unknown;
  tool_span_id?: unknown;
  type?: unknown;
};

/** 从 role=tool 消息抽取出的工具返回，用于并入对应的 tool_call */
type ToolCallResponse = {
  isError: boolean;
  response: unknown;
};

/**
 * @description 解析模型 Span 时间流：系统 / 工具定义独立成组，输入输出按 messages 编号、parts 顺序连行
 */
export function parseModelTimeline(attributes: Record<string, unknown>): LlmModelTimeline {
  const availableTools = parseAvailableTools(attributes);
  const descriptionMap = availableTools.reduce<Record<string, string>>((acc, item) => {
    if (item.name) acc[item.name] = item.description;
    return acc;
  }, {});
  const inputMessages = parseTimelineMessages(pickList(attributes, ['gen_ai.input.messages']), 'input', descriptionMap);
  const outputMessages = parseTimelineMessages(
    pickList(attributes, ['gen_ai.output.messages']),
    'output',
    descriptionMap
  );
  const errorCount = [...inputMessages, ...outputMessages].filter(item => item.isError).length;

  return {
    systemPrompts: parseSystemPrompts(attributes),
    availableTools,
    inputMessages,
    outputMessages,
    errorCount,
  };
}

/** 收集所有 tool_call Part 的调用 ID，用于判断返回 Part 是否已配对 */
function collectToolCallIds(messages: unknown[]): Set<string> {
  const result = new Set<string>();
  for (const message of messages) {
    if (!isRecord(message)) continue;
    const raw = message as LlmMessage;
    for (const part of toMessageParts(raw)) {
      const type = resolvePartType(part);
      // 返回 Part（显式 tool_call_response 或 role=tool 的隐式返回）不参与配对
      if (!isToolCallType(type) || isResponsePart(part, raw)) continue;
      const id = String(part.id || part.tool_call_id || '').trim();
      if (id) result.add(id);
    }
  }
  return result;
}

/**
 * 收集所有消息里的工具返回 Part，按 id 供对应 tool_call 补全返回结果。
 * 返回不一定落在 role=tool 消息里，也可能与普通文本混在同一条 role=user 消息中，因此按 Part 类型收集。
 * 同一 id 出现多次时保留首个有效返回，避免重复 Part 互相覆盖。
 */
function collectToolResponses(messages: unknown[]): Map<string, ToolCallResponse> {
  const result = new Map<string, ToolCallResponse>();
  for (const message of messages) {
    if (!isRecord(message)) continue;
    const raw = message as LlmMessage;
    const messageError = isErrorLike(raw);
    for (const part of toMessageParts(raw)) {
      if (!isResponsePart(part, raw)) continue;
      const id = resolveResponseId(part, raw);
      if (!id) continue;
      const current = result.get(id);
      if (current?.response !== undefined) continue;
      result.set(id, {
        response: part.response !== undefined ? parseJsonValue(part.response) : parseJsonValue(part.content),
        isError: messageError || isErrorLike(part),
      });
    }
  }
  return result;
}

/** 优先取 part 上的描述，否则回落到 tool.definitions */
function getToolDescription(definitions: Record<string, string>, name: string, part?: LlmMessagePart): string {
  const fromPart = stringifyContent(part?.description).trim();
  if (fromPart) return fromPart;
  return definitions[name] || '';
}

function isErrorLike(value: unknown): boolean {
  if (!isRecord(value)) return false;
  if (value.is_error === true || value.error === true) return true;
  const status = String(value.status || value.level || '').toLowerCase();
  if (['error', 'exception', 'fail', 'failed'].includes(status)) return true;
  if (value.error != null && value.error !== false && value.error !== '') return true;
  return false;
}

/** 返回 Part 若已存在同 id 的 tool_call，则并入调用行展示、不再单独成行；未配对时保留兜底展示 */
function isPairedResponsePart(part: LlmMessagePart, message: LlmMessage, callIds: Set<string>): boolean {
  if (!isResponsePart(part, message)) return false;
  const id = resolveResponseId(part, message);
  return Boolean(id) && callIds.has(id);
}

/** 是否为工具返回 Part：显式 tool_call_response，或 role=tool 消息里非显式工具调用的隐式返回 */
function isResponsePart(part: LlmMessagePart, message: LlmMessage): boolean {
  if (resolvePartType(part) === 'tool_call_response') return true;
  // 显式工具调用即便落在 role=tool 消息里也只是调用，不能算作隐式返回
  if (isExplicitToolCall(part)) return false;
  return String(message.role || '').toLowerCase() === 'tool';
}

/** 是否为显式工具调用：显式标注调用类型，或缺省 type 但带调用参数 */
function isExplicitToolCall(part: LlmMessagePart): boolean {
  const type = String(part.type || '').toLowerCase();
  if (type && type !== 'tool_call_response' && isToolCallType(type)) return true;
  return part.arguments !== undefined;
}

function isToolCallType(type: string): boolean {
  return ['function', 'function_call', 'functioncall', 'tool_call', 'tool_call_response', 'tool_use'].includes(type);
}

function normalizePart(value: unknown): LlmMessagePart | null {
  if (!isRecord(value)) return null;
  const fn = isRecord(value.function) ? value.function : null;
  return {
    ...value,
    name: value.name ?? fn?.name,
    arguments: value.arguments ?? value.input ?? value.parameters ?? fn?.arguments,
  };
}

function parseAvailableTools(attributes: Record<string, unknown>): LlmToolDefinition[] {
  return pickList(attributes, ['gen_ai.tool.definitions'])
    .map((item, index) => {
      if (!isRecord(item)) return null;
      const name = String(item.name || '').trim();
      if (!name && item.description == null && item.parameters == null) return null;
      return {
        name: name || `tool-${index + 1}`,
        description: stringifyContent(item.description).trim(),
        parameters: parseJsonValue(item.parameters) ?? {},
      };
    })
    .filter((item): item is LlmToolDefinition => Boolean(item));
}

function parseSystemPrompts(attributes: Record<string, unknown>): LlmTextItem[] {
  return pickList(attributes, ['gen_ai.system_instructions'])
    .map((item, index) => {
      if (typeof item === 'string') return toTextItem(`system-${index}`, item);
      if (!isRecord(item)) return null;
      const type = String(item.type || 'text').toLowerCase();
      if (type !== 'text') return null;
      return toTextItem(`system-${index}`, item.content);
    })
    .filter((item): item is LlmTextItem => Boolean(item));
}

function parseTimelineMessages(
  messages: unknown[],
  tab: 'input' | 'output',
  descriptionMap: Record<string, string>
): LlmTimelineMessage[] {
  const result: LlmTimelineMessage[] = [];
  // 返回结果可能混在任意 role 的消息里，先按 tool_call_response / role=tool 全局收集再并入对应 tool_call
  const toolResponses = collectToolResponses(messages);
  // 已存在对应 tool_call 的返回 Part 会被并入调用行，渲染时跳过，避免重复成行
  const pairedResponseIds = collectToolCallIds(messages);
  // 展示序号按实际渲染的消息依次递增，避免跳过 tool 消息后出现跳号
  let displayIndex = 0;

  for (const [index, message] of messages.entries()) {
    // messageId 用原始下标，保证被跳过的返回 Part 不影响其它消息的身份稳定
    const messageId = `${tab}-${index + 1}`;
    if (typeof message === 'string') {
      const text = message.trim();
      if (!text) continue;
      displayIndex += 1;
      const messageIndex = displayIndex;
      result.push({
        id: messageId,
        index: messageIndex,
        isError: false,
        parts: [
          {
            id: `${messageId}-0`,
            role: tab === 'output' ? 'model' : 'user',
            content: text,
            isError: false,
            messageIndex,
            searchBlockId: `${tab}:timeline:${messageId}:${messageId}-0`,
            showIndex: true,
          },
        ],
        tab,
      });
      continue;
    }
    if (!isRecord(message)) continue;
    const raw = message as LlmMessage;
    const role = String(raw.role || '').toLowerCase();
    // 先按「下一条」预算序号，parts 为空时不提交该序号
    const messageIndex = displayIndex + 1;
    const parts: LlmTimelinePart[] = [];
    const messageError = isErrorLike(raw);

    for (const [partIndex, rawPart] of toMessageParts(raw).entries()) {
      // 已并入 tool_call 的返回 Part 跳过，但同条消息内的文本 / 未配对返回继续展示
      if (isPairedResponsePart(rawPart, raw, pairedResponseIds)) continue;
      const part = toTimelinePart(
        rawPart,
        {
          messageError,
          messageId,
          messageIndex,
          messageToolCallId: String(raw.tool_call_id || '').trim(),
          partIndex,
          role,
          isResponse: isResponsePart(rawPart, raw),
          tab,
        },
        descriptionMap,
        toolResponses
      );
      if (part) parts.push(part);
    }

    if (!parts.length) continue;

    displayIndex = messageIndex;

    const isAssistant = role === 'assistant' || role === 'model';
    const hasText = parts.some(item => item.role === 'user' || (item.role === 'model' && !item.isPlaceholder));
    if (isAssistant && !hasText && parts.some(item => item.role === 'tool')) {
      parts.unshift({
        id: `${messageId}-placeholder`,
        role: 'model',
        content: '',
        isError: messageError,
        isPlaceholder: true,
        messageIndex,
        searchBlockId: `${tab}:timeline:${messageId}:placeholder`,
        showIndex: true,
      });
    }

    if (parts[0]) parts[0].showIndex = true;
    for (const item of parts.slice(1)) {
      item.showIndex = false;
    }

    result.push({
      id: messageId,
      index: messageIndex,
      isError: messageError || parts.some(item => item.isError),
      parts,
      tab,
    });
  }

  return result;
}

/** 推断 part 类型：缺省时按 name / arguments / response 判定是否工具调用 */
function resolvePartType(part: LlmMessagePart): string {
  return String(
    part.type || (part.name || part.arguments !== undefined || part.response !== undefined ? 'tool_call' : 'text')
  ).toLowerCase();
}

/** 工具返回 Part 的调用 ID：Part 上优先，回落到消息的 tool_call_id */
function resolveResponseId(part: LlmMessagePart, message: LlmMessage): string {
  return String(part.id || part.tool_call_id || message.tool_call_id || '').trim();
}

function resolveRole(partType: string, messageRole: string): LlmTimelineRole | null {
  if (partType === 'reasoning') return 'thinking';
  if (isToolCallType(partType)) return 'tool';
  if (partType && partType !== 'text') return null;
  if (messageRole === 'user') return 'user';
  if (messageRole === 'assistant' || messageRole === 'model') return 'model';
  if (messageRole === 'system') return null;
  return messageRole === 'tool' ? 'tool' : 'model';
}

function toMessageParts(message: LlmMessage): LlmMessagePart[] {
  const parts: LlmMessagePart[] = [];
  if (Array.isArray(message.parts)) {
    parts.push(...message.parts.map(normalizePart).filter(item => Boolean(item)));
  } else if (Array.isArray(message.content)) {
    parts.push(...message.content.map(normalizePart).filter(item => Boolean(item)));
  } else if (message.content != null && message.content !== '') {
    parts.push({ type: 'text', content: message.content });
  }

  const hasToolCall = parts.some(part => isToolCallType(String(part.type || '').toLowerCase()));
  if (!hasToolCall && Array.isArray(message.tool_calls)) {
    parts.push(...message.tool_calls.map(normalizePart).filter(item => Boolean(item)));
  }
  return parts;
}

function toTimelinePart(
  part: LlmMessagePart,
  meta: {
    isResponse: boolean;
    messageError: boolean;
    messageId: string;
    messageIndex: number;
    messageToolCallId: string;
    partIndex: number;
    role: string;
    tab: 'input' | 'output';
  },
  descriptionMap: Record<string, string>,
  toolResponses: Map<string, ToolCallResponse>
): LlmTimelinePart | null {
  const type = resolvePartType(part);
  const role = resolveRole(type, meta.role);
  if (!role) return null;

  const id = `${meta.messageId}-${meta.partIndex}`;
  const searchBlockId = `${meta.tab}:timeline:${meta.messageId}:${id}`;
  if (role === 'tool') {
    const toolName = String(part.name || '').trim();
    const toolCallId = String(part.id || part.tool_call_id || meta.messageToolCallId).trim();
    // 合并按 id 匹配的工具返回（含混在非 tool 消息里的 tool_call_response）
    const matched = toolCallId ? toolResponses.get(toolCallId) : undefined;
    // 返回 Part（显式 tool_call_response 或 role=tool 隐式返回）本体即返回结果，未配对时用 content 兜底，
    // 不因带 name / arguments 而丢弃
    const ownResponse =
      part.response !== undefined
        ? parseJsonValue(part.response)
        : meta.isResponse
          ? parseJsonValue(part.content)
          : undefined;
    const response = ownResponse !== undefined ? ownResponse : matched?.response;
    return {
      id,
      role,
      content: '',
      description: getToolDescription(descriptionMap, toolName, part),
      isError: meta.messageError || isErrorLike(part) || matched?.isError === true,
      messageIndex: meta.messageIndex,
      searchBlockId,
      showIndex: false,
      toolName,
      ...(toolCallId ? { toolCallId } : {}),
      spanId: String(part.span_id || part.spanId || part.tool_span_id || '').trim(),
      arguments: parseJsonValue(part.arguments),
      ...(response !== undefined ? { response } : {}),
    };
  }

  const content = stringifyContent(part.content ?? part.text).trim();
  if (!content) return null;
  return {
    id,
    role,
    content,
    isError: meta.messageError || isErrorLike(part),
    messageIndex: meta.messageIndex,
    searchBlockId,
    showIndex: false,
  };
}
