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
import { EMPTY_TEXT } from '../constants';
import { formatElapsed, formatMicroTime, formatTokens } from './formatters';

import type { IIoSummaryCell, ILlmTraceItem, ISessionRow, ITokensCell, ITraceRow, LlmStatus } from '../typings';

export function toSessionRow(item: ILlmTraceItem): ISessionRow {
  const children = (item.childs || []).map(toTraceRow);
  const elapsed = Math.max(0, item.end_time - item.start_time);
  return {
    key: item.group_id,
    sessionId: item.group_id,
    userId: item.user_id,
    lastActiveText: formatMicroTime(item.end_time),
    traceCountText: `${children.length}`,
    ioSummary: toIoSummary(item),
    elapsedText: formatElapsed(elapsed),
    elapsedDetailText: formatElapsed(elapsed, true),
    tokens: toTokensCell(item.input_tokens || 0, item.output_tokens || 0),
    status: toStatus(item.status),
    children,
  };
}

export function toTraceRow(item: ILlmTraceItem): ITraceRow {
  const inputTokens = item.input_tokens || 0;
  const outputTokens = item.output_tokens || 0;
  const elapsed = Math.max(0, item.end_time - item.start_time);
  return {
    key: item.trace_id || item.group_id,
    traceId: item.trace_id || item.group_id,
    sessionId: item.conversation_id || EMPTY_TEXT,
    userId: item.user_id,
    lastActiveValue: item.end_time,
    lastActiveText: formatMicroTime(item.end_time),
    ioSummary: toIoSummary(item),
    elapsedValue: elapsed,
    elapsedText: formatElapsed(elapsed),
    elapsedDetailText: formatElapsed(elapsed, true),
    tokensTotalValue: inputTokens + outputTokens,
    tokens: toTokensCell(inputTokens, outputTokens),
    status: toStatus(item.status),
  };
}

/** 输入 / 输出摘要：接口分别返回逻辑根 Span 的最后一条用户文本与助手文本 */
function toIoSummary(item: ILlmTraceItem): IIoSummaryCell {
  return {
    input: item.input?.trim() || EMPTY_TEXT,
    output: item.output?.trim() || EMPTY_TEXT,
  };
}

/** 只透传接口约定的 success / error，其余回退空串由表格占位 */
function toStatus(status?: string): '' | LlmStatus {
  return status === 'success' || status === 'error' ? status : '';
}

/** Tokens 单元格：总量取输入 + 输出之和，缓存读写两个字段暂不展示 */
function toTokensCell(inputTokens: number, outputTokens: number): ITokensCell {
  return {
    totalText: formatTokens(inputTokens + outputTokens),
    inputText: formatTokens(inputTokens),
    outputText: formatTokens(outputTokens),
  };
}
