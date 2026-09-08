import { EMPTY_TEXT, IO_SUMMARY_SEPARATOR } from '../constants';
import { formatElapsed, formatMicroTime, formatTokens } from './formatters';

import type { ILlmTraceItem, ISessionRow, ITokensCell, ITraceRow } from '../typings';

/** Tokens 单元格：总量取输入 + 输出之和，缓存读写两个字段暂不展示 */
function toTokensCell(inputTokens: number, outputTokens: number): ITokensCell {
  return {
    totalText: formatTokens(inputTokens + outputTokens),
    inputText: formatTokens(inputTokens),
    outputText: formatTokens(outputTokens),
  };
}

/** 输入 / 输出摘要：接口分别返回逻辑根 Span 的最后一条用户文本与助手文本 */
function toIoSummary(item: ILlmTraceItem): string {
  const input = item.input?.trim();
  const output = item.output?.trim();
  if (!input && !output) return EMPTY_TEXT;
  return `${input || EMPTY_TEXT}${IO_SUMMARY_SEPARATOR}${output || EMPTY_TEXT}`;
}

export function toTraceRow(item: ILlmTraceItem): ITraceRow {
  const inputTokens = item.input_tokens || 0;
  const outputTokens = item.output_tokens || 0;
  return {
    key: item.trace_id || item.group_id,
    traceId: item.trace_id || item.group_id,
    userId: item.user_id,
    // 接口按 trace_id 分组时不返回会话 ID，待后端补齐后在此映射
    sessionId: '',
    startTimeValue: item.start_time,
    startTimeText: formatMicroTime(item.start_time),
    ioSummary: toIoSummary(item),
    elapsedValue: item.elapsed_time,
    elapsedText: formatElapsed(item.elapsed_time),
    tokensTotalValue: inputTokens + outputTokens,
    tokens: toTokensCell(inputTokens, outputTokens),
    // 接口暂未返回状态，待后端补齐后在此映射
    status: '',
  };
}

export function toSessionRow(item: ILlmTraceItem): ISessionRow {
  const children = (item.childs || []).map(toTraceRow);
  return {
    key: item.group_id,
    sessionId: item.group_id,
    userId: item.user_id,
    firstActiveText: formatMicroTime(item.start_time),
    // 会话持续时间以根 Span 开始时间为起点，末次活动时间即起点加持续时长
    lastActiveText: formatMicroTime(item.start_time + item.elapsed_time),
    traceCountText: `${children.length}`,
    tokens: toTokensCell(item.input_tokens || 0, item.output_tokens || 0),
    status: '',
    children,
  };
}
