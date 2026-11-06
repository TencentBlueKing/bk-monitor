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
  tool_call_id?: unknown;
  tool_span_id?: unknown;
  text?: unknown;
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

function isErrorLike(value: unknown): boolean {
  if (!isRecord(value)) return false;
  if (value.is_error === true || value.error === true) return true;
  const status = String(value.status || value.level || '').toLowerCase();
  if (['error', 'exception', 'fail', 'failed'].includes(status)) return true;
  if (value.error != null && value.error !== false && value.error !== '') return true;
  return false;
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
  // role=tool 的返回消息不单独成行，先按 id 收集再并入对应的 tool_call
  const toolResponses = collectToolResponses(messages);
  // 展示序号按实际渲染的消息依次递增，避免跳过 tool 消息后出现跳号
  let displayIndex = 0;

  for (const [index, message] of messages.entries()) {
    // messageId 用原始下标，保证被跳过的 tool 消息不影响其它消息的身份稳定
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
    // role=tool 的返回消息已并入对应 tool_call，不再单独渲染
    if (role === 'tool') continue;
    // 先按「下一条」预算序号，parts 为空时不提交该序号
    const messageIndex = displayIndex + 1;
    const parts: LlmTimelinePart[] = [];
    const messageError = isErrorLike(raw);

    for (const [partIndex, rawPart] of toMessageParts(raw).entries()) {
      const part = toTimelinePart(
        rawPart,
        {
          messageError,
          messageId,
          messageIndex,
          partIndex,
          role,
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

/**
 * 收集 role=tool 消息里的 tool_call_response，按 id 供对应 tool_call 补全返回结果。
 * 同一 id 出现多次时保留首个有效返回，避免重复消息互相覆盖。
 */
function collectToolResponses(messages: unknown[]): Map<string, ToolCallResponse> {
  const result = new Map<string, ToolCallResponse>();
  for (const message of messages) {
    if (!isRecord(message)) continue;
    const raw = message as LlmMessage;
    if (String(raw.role || '').toLowerCase() !== 'tool') continue;
    const messageError = isErrorLike(raw);
    const messageToolCallId = String(raw.tool_call_id || '').trim();
    for (const part of toMessageParts(raw)) {
      const type = String(part.type || '').toLowerCase();
      if (type !== 'tool_call_response') continue;
      const id = String(part.id || part.tool_call_id || messageToolCallId).trim();
      if (!id) continue;
      const current = result.get(id);
      if (current && current.response !== undefined) continue;
      result.set(id, {
        response: part.response !== undefined ? parseJsonValue(part.response) : parseJsonValue(part.content),
        isError: messageError || isErrorLike(part),
      });
    }
  }
  return result;
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
    parts.push(...message.parts.map(normalizePart).filter((item) => Boolean(item)));
  } else if (Array.isArray(message.content)) {
    parts.push(...message.content.map(normalizePart).filter((item) => Boolean(item)));
  } else if (message.content != null && message.content !== '') {
    parts.push({ type: 'text', content: message.content });
  }

  const hasToolCall = parts.some(part => isToolCallType(String(part.type || '').toLowerCase()));
  if (!hasToolCall && Array.isArray(message.tool_calls)) {
    parts.push(...message.tool_calls.map(normalizePart).filter((item) => Boolean(item)));
  }
  return parts;
}

function toTimelinePart(
  part: LlmMessagePart,
  meta: {
    messageError: boolean;
    messageId: string;
    messageIndex: number;
    partIndex: number;
    role: string;
    tab: 'input' | 'output';
  },
  descriptionMap: Record<string, string>,
  toolResponses: Map<string, ToolCallResponse>
): LlmTimelinePart | null {
  const type = String(
    part.type || (part.name || part.arguments !== undefined || part.response !== undefined ? 'tool_call' : 'text')
  ).toLowerCase();
  const role = resolveRole(type, meta.role);
  if (!role) return null;

  const id = `${meta.messageId}-${meta.partIndex}`;
  const searchBlockId = `${meta.tab}:timeline:${meta.messageId}:${id}`;
  if (role === 'tool') {
    const toolName = String(part.name || '').trim();
    const toolCallId = String(part.id || part.tool_call_id || '').trim();
    // 合并 role=tool 消息里按 id 匹配的 tool_call_response
    const matched = toolCallId ? toolResponses.get(toolCallId) : undefined;
    const response =
      part.response !== undefined
        ? parseJsonValue(part.response)
        : type === 'tool_call_response'
          ? parseJsonValue(part.content)
          : matched?.response;
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

/** 优先取 part 上的描述，否则回落到 tool.definitions */
function getToolDescription(definitions: Record<string, string>, name: string, part?: LlmMessagePart): string {
  const fromPart = stringifyContent(part?.description).trim();
  if (fromPart) return fromPart;
  return definitions[name] || '';
}
