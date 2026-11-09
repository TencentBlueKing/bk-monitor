import { customFormatTime, formatDuration } from '../../../../components/trace-view/utils/date';

import { isRecord } from './helpers';

import type { LlmModelTimeline, LlmTimelineMessage, LlmTimelinePart, LlmToolCall } from './typings';

/** OTLP / list_tool_calls status.code === 2 视为执行失败 */
const TOOL_CALL_STATUS_ERROR = 2;

/**
 * @description 工具行耗时：有开始时间时显示 HH:mm:ss，有耗时时追加 (耗时)，耗时单位与 span-row 保持一致
 */
export function formatToolCallDuration(startTime: number | null, elapsedTime: number | null): string {
  const startText = startTime != null ? customFormatTime(startTime, 'HH:mm:ss') : '';
  const elapsedText = elapsedTime != null ? formatDuration(elapsedTime) : '';
  if (startText && elapsedText) return `${startText} (${elapsedText})`;
  return startText || elapsedText;
}

function toNumberOrNull(value: unknown): number | null {
  if (typeof value === 'number' && Number.isFinite(value)) return value;
  if (typeof value === 'string' && value.trim() && Number.isFinite(Number(value))) return Number(value);
  return null;
}

function normalizeToolCallStatus(value: unknown): Pick<LlmToolCall, 'isError' | 'statusMessage'> {
  if (!isRecord(value)) return { isError: false, statusMessage: '' };
  return {
    isError: Number(value.code) === TOOL_CALL_STATUS_ERROR,
    statusMessage: typeof value.message === 'string' ? value.message.trim() : '',
  };
}

/** 将 list_tool_calls 单条记录规范成前端使用的结构 */
export function normalizeToolCall(value: unknown): LlmToolCall | null {
  if (!isRecord(value)) return null;
  const status = normalizeToolCallStatus(value.status);
  return {
    spanId: String(value.span_id || '').trim(),
    toolCallId: String(value.tool_call_id || '').trim(),
    toolName: String(value.tool_name || '').trim(),
    startTime: toNumberOrNull(value.start_time),
    elapsedTime: toNumberOrNull(value.elapsed_time),
    isError: status.isError,
    statusMessage: status.statusMessage,
  };
}

/**
 * 将时间流工具行与接口记录对齐：tool_call_id → span_id → 未占用的唯一 tool_name
 */
export function matchTimelineToolCalls(parts: LlmTimelinePart[], toolCalls: LlmToolCall[]): Map<string, LlmToolCall> {
  const result = new Map<string, LlmToolCall>();
  const unused = toolCalls.slice();
  const take = (predicate: (call: LlmToolCall) => boolean) => {
    const index = unused.findIndex(predicate);
    if (index < 0) return undefined;
    return unused.splice(index, 1)[0];
  };

  for (const part of parts) {
    const toolCallId = part.toolCallId?.trim();
    if (!toolCallId) continue;
    const matched = take(call => call.toolCallId === toolCallId);
    if (matched) result.set(part.id, matched);
  }

  for (const part of parts) {
    if (result.has(part.id)) continue;
    const spanId = part.spanId?.trim();
    if (!spanId) continue;
    const matched = take(call => call.spanId === spanId);
    if (matched) result.set(part.id, matched);
  }

  for (const part of parts) {
    if (result.has(part.id)) continue;
    const toolName = part.toolName?.trim();
    if (!toolName) continue;
    const sameName = unused.filter(call => call.toolName === toolName);
    if (sameName.length !== 1) continue;
    const matched = take(call => call === sameName[0]);
    if (matched) result.set(part.id, matched);
  }

  return result;
}

/**
 * 命中 list_tool_calls 的工具行以接口 status 为准，未命中保留属性启发式。
 * 异常计数按回写后的消息数，保证和筛选列表一致。
 */
export function applyToolCallStatus(
  timeline: LlmModelTimeline,
  toolCallMap: Map<string, LlmToolCall>
): LlmModelTimeline {
  const inputMessages = overlayToolCallStatus(timeline.inputMessages, toolCallMap);
  const outputMessages = overlayToolCallStatus(timeline.outputMessages, toolCallMap);
  if (inputMessages === timeline.inputMessages && outputMessages === timeline.outputMessages) {
    return timeline;
  }
  return {
    ...timeline,
    inputMessages,
    outputMessages,
    errorCount: [...inputMessages, ...outputMessages].filter(item => item.isError).length,
  };
}

function overlayToolCallStatus(
  messages: LlmTimelineMessage[],
  toolCallMap: Map<string, LlmToolCall>
): LlmTimelineMessage[] {
  let changed = false;
  const next = messages.map(message => {
    let partsChanged = false;
    const parts = message.parts.map(part => {
      if (part.role !== 'tool') return part;
      const matched = toolCallMap.get(part.id);
      if (!matched || part.isError === matched.isError) return part;
      partsChanged = true;
      return { ...part, isError: matched.isError };
    });
    const isError = parts.some(item => item.isError);
    if (!partsChanged && isError === message.isError) return message;
    changed = true;
    return { ...message, parts, isError };
  });
  return changed ? next : messages;
}
