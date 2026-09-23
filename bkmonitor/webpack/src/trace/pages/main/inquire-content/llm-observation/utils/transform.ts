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

import { formatDuration } from '../../../../../components/trace-view/utils/date';
import { formatTokenCount, getByPath, pickNumber, stringifyContent } from '../../../llm-observation/utils/helpers';
import { flattenKvPairs, parseInputObservation } from '../../../llm-observation/utils/parse-input';
import { parseOutputObservation } from '../../../llm-observation/utils/parse-output';
import { parseToolObservation } from '../../../llm-observation/utils/parse-tool';

import type {
  LlmExecutionFilter,
  LlmFlowSpan,
  LlmFlowTrace,
  LlmIoPreview,
  LlmOverviewStats,
  LlmSpanKind,
  LlmSpanRowView,
  LlmStatCard,
  LlmTraceView,
} from './typings';

/**
 * list_llm_flows 响应 → 页面视图模型：Span 归类、统计、筛选扁平化与 I/O 预览。
 * 解析逻辑复用 main/llm-observation 下的 parse-* 工具。
 */

/** OTLP StatusCode: 0 UNSET, 1 OK, 2 ERROR */
const STATUS_ERROR_CODE = 2;

/** Span 类型徽章对应的 icon-monitor 后缀（与 FILTER_TABS 一致） */
export const LLM_KIND_CLASS: Record<LlmSpanKind, string> = {
  AGENT: 'Agent',
  LLM: 'LLM',
  TOOL: 'Tool',
};

/**
 * list_llm_flows / list_llm_spans 文档约定的页面节点类型。
 * 额外收录后端 adapter 已登记的同族 operation，避免产品差异操作掉出三类。
 */
const SPAN_KIND_BY_OPERATION: Record<string, LlmSpanKind> = {
  invoke_agent: 'AGENT',
  invoke_workflow: 'AGENT',
  create_agent: 'AGENT',
  plan: 'AGENT',
  chat: 'LLM',
  text_completion: 'LLM',
  generate_content: 'LLM',
  fetch_response: 'LLM',
  embeddings: 'LLM',
  execute_tool: 'TOOL',
};

/** gen_ai.usage 在不同 SDK / 版本下字段名可能不同，按优先级累加 */
const INPUT_TOKEN_KEYS = ['gen_ai.usage.input_tokens', 'gen_ai.usage.prompt_tokens'];
const OUTPUT_TOKEN_KEYS = ['gen_ai.usage.output_tokens', 'gen_ai.usage.completion_tokens'];
const CACHE_READ_TOKEN_KEYS = ['gen_ai.usage.cache_read.input_tokens'];
const CACHE_WRITE_TOKEN_KEYS = [
  'gen_ai.usage.cache_write.input_tokens',
  'gen_ai.usage.cache_creation.input_tokens',
];

const TOKEN_UNITS: [number, string][] = [
  [1e6, 'm'],
  [1e3, 'k'],
];

/** flattenVisibleSpanRows 内部使用的 Span 树节点 */
type SpanTreeNode = {
  children: SpanTreeNode[];
  span: LlmFlowSpan;
};

/** 将 Token 数量格式化为 14.2m / 42k，不足 1000 时原样输出 */
export function formatCompactToken(value: number): string {
  if (!Number.isFinite(value) || value <= 0) return '0';
  for (const [threshold, unit] of TOKEN_UNITS) {
    if (value >= threshold) {
      const compact = value / threshold;
      const text = Number.isInteger(compact) ? `${compact}` : compact.toFixed(1).replace(/\.0$/, '');
      return `${text}${unit}`;
    }
  }
  return `${value}`;
}

/** 统计卡耗时：数字与单位拆开，对齐设计稿 1.82 + s */
export function splitDuration(microseconds: number): { unit: string; value: string } {
  const text = formatDuration(Math.max(0, microseconds));
  const matched = text.match(/^([\d.]+)(.*)$/);
  if (!matched) return { value: text || '0', unit: '' };
  return { value: matched[1], unit: matched[2] };
}

/** OTLP status.code === 2 视为 Span 失败 */
export function isErrorSpan(span: LlmFlowSpan): boolean {
  return Number(span.status?.code) === STATUS_ERROR_CODE;
}

/** 节点类型由 gen_ai.operation.name 决定，与树中位置无关；未登记操作返回 undefined */
export function resolveSpanKind(span: LlmFlowSpan): LlmSpanKind | undefined {
  const operation = String(getByPath(span.attributes || {}, 'gen_ai.operation.name') || '')
    .trim()
    .toLowerCase();
  return SPAN_KIND_BY_OPERATION[operation];
}

/** 深度优先扫描 Span 树，取首个非空 gen_ai.conversation.id */
export function extractConversationId(spans: LlmFlowSpan[]): string {
  for (const span of walkSpans(spans)) {
    const value = getByPath(span.attributes || {}, 'gen_ai.conversation.id');
    if (value != null && String(value).trim()) return String(value);
  }
  return '';
}

/** 将 API 返回的 childs 树展平为 Span 列表（深度优先） */
export function collectSpanList(nodes: LlmFlowSpan[]): LlmFlowSpan[] {
  return [...walkSpans(nodes)];
}

/** 优先用 traces.conversation_id，没有再从已加载 Span 回退 */
export function pickConversationId(traces: LlmFlowTrace[]): string {
  for (const trace of traces) {
    const value = String(trace.conversation_id || '').trim();
    if (value) return value;
  }
  return extractConversationId(traces.flatMap(item => collectSpanList(item.flow)));
}

/** 统计卡：耗时 / Token / 缓存优先用概览汇总，模型与工具次数只统计已拉取 flow */
export function buildStatCards(
  traces: LlmFlowTrace[],
  t: (key: string) => string,
  overview?: LlmOverviewStats | null
): LlmStatCard[] {
  const spans = traces.flatMap(item => collectSpanList(item.flow));
  let inputTokens = 0;
  let outputTokens = 0;
  let cacheRead = 0;
  let cacheWrite = 0;
  // let modelCount = 0;
  // let toolCount = 0;
  let minStart = Number.POSITIVE_INFINITY;
  let maxEnd = 0;

  for (const span of spans) {
    const attrs = span.attributes || {};
    inputTokens += pickNumber(attrs, INPUT_TOKEN_KEYS);
    outputTokens += pickNumber(attrs, OUTPUT_TOKEN_KEYS);
    cacheRead += pickNumber(attrs, CACHE_READ_TOKEN_KEYS);
    cacheWrite += pickNumber(attrs, CACHE_WRITE_TOKEN_KEYS);
    // const kind = resolveSpanKind(span);
    // if (kind === 'LLM') modelCount += 1;
    // if (kind === 'TOOL') toolCount += 1;
    if (span.start_time < minStart) minStart = span.start_time;
    if (span.end_time > maxEnd) maxEnd = span.end_time;
  }

  if (overview) {
    if (overview.input_tokens != null) inputTokens = overview.input_tokens;
    if (overview.output_tokens != null) outputTokens = overview.output_tokens;
    if (overview.cache_read_input_tokens != null) cacheRead = overview.cache_read_input_tokens;
    if (overview.cache_write_input_tokens != null) cacheWrite = overview.cache_write_input_tokens;
  }

  const duration =
    overview?.elapsed_time != null
      ? Math.max(0, overview.elapsed_time)
      : Number.isFinite(minStart)
        ? Math.max(0, maxEnd - minStart)
        : 0;
  const totalTokens = overview?.total_tokens != null ? overview.total_tokens : inputTokens + outputTokens;
  const durationParts = splitDuration(duration);

  return [
    { key: 'duration', label: t('总耗时'), value: durationParts.value, unit: durationParts.unit },
    // { key: 'model', label: t('模型调用'), value: formatTokenCount(modelCount) },
    { key: 'input', label: t('输入 Tokens'), value: formatTokenCount(inputTokens) },
    { key: 'output', label: t('输出 Tokens'), value: formatTokenCount(outputTokens) },
    { key: 'total', label: t('总 Tokens'), value: formatTokenCount(totalTokens), theme: 'success' },
    { key: 'cacheRead', label: t('缓存读数'), value: formatTokenCount(cacheRead) },
    { key: 'cacheWrite', label: t('缓存写入'), value: formatTokenCount(cacheWrite) },
    // { key: 'tool', label: t('工具调用'), value: formatTokenCount(toolCount) },
  ];
}

/** 单条 Trace 卡片数据：优先接口汇总字段，flow 未加载时用已加载 Span 累加 */
export function buildTraceView(
  trace: LlmFlowTrace,
  currentTraceId: string,
  flowLoaded = Boolean(trace.flow?.length)
): LlmTraceView {
  const spans = collectSpanList(trace.flow);
  let inputTokens = 0;
  let outputTokens = 0;
  let errorCount = 0;
  let minStart = Number.POSITIVE_INFINITY;
  let maxEnd = 0;

  for (const span of spans) {
    const attrs = span.attributes || {};
    inputTokens += pickNumber(attrs, INPUT_TOKEN_KEYS);
    outputTokens += pickNumber(attrs, OUTPUT_TOKEN_KEYS);
    if (isErrorSpan(span)) errorCount += 1;
    if (span.start_time < minStart) minStart = span.start_time;
    if (span.end_time > maxEnd) maxEnd = span.end_time;
  }

  const nextInputTokens = trace.input_tokens != null ? trace.input_tokens : inputTokens;
  const nextOutputTokens = trace.output_tokens != null ? trace.output_tokens : outputTokens;

  return {
    traceId: trace.trace_id,
    isCurrent: trace.trace_id === currentTraceId,
    startTime: trace.start_time != null ? trace.start_time : Number.isFinite(minStart) ? minStart : 0,
    title: String(trace.input || '').trim() || pickTraceTitle(trace.flow),
    input: String(trace.input || '').trim(),
    output: String(trace.output || '').trim(),
    userId: String(trace.user_id || '').trim(),
    conversationId: String(trace.conversation_id || '').trim() || extractConversationId(trace.flow),
    spanCount: spans.length,
    errorCount,
    elapsedTime:
      trace.elapsed_time != null
        ? Math.max(0, trace.elapsed_time)
        : Number.isFinite(minStart)
          ? Math.max(0, maxEnd - minStart)
          : 0,
    inputTokens: nextInputTokens,
    outputTokens: nextOutputTokens,
    totalTokens: trace.total_tokens != null ? trace.total_tokens : nextInputTokens + nextOutputTokens,
    flowLoaded,
  };
}

/** 工具栏各筛选 Tab 上的数量角标（仅统计已加载 flow 的 Span） */
export function countSpanKinds(traces: LlmFlowTrace[]): Record<LlmExecutionFilter, number> {
  const spans = traces.flatMap(item => collectSpanList(item.flow));
  return {
    all: spans.length,
    agent: spans.filter(item => resolveSpanKind(item) === 'AGENT').length,
    llm: spans.filter(item => resolveSpanKind(item) === 'LLM').length,
    tool: spans.filter(item => resolveSpanKind(item) === 'TOOL').length,
    error: spans.filter(item => isErrorSpan(item)).length,
  };
}

/** 按展开态、类型筛选和关键字展开为表格行，保留匹配节点的祖先以维持层级 */
export function flattenVisibleSpanRows(
  flow: LlmFlowSpan[],
  options: {
    expandedSpanIds: Set<string>;
    filter: LlmExecutionFilter;
    keyword: string;
  }
): LlmSpanRowView[] {
  const trees = toTree(flow);
  const keyword = options.keyword.trim().toLowerCase();
  const rows: LlmSpanRowView[] = [];

  const walk = (
    nodes: SpanTreeNode[],
    depth: number,
    ancestorsExpanded: boolean,
    lineGuideLevel: number
  ) => {
    const visibleNodes = nodes.filter(node => nodeMatchesOrHasMatch(node, options.filter, keyword));
    visibleNodes.forEach((node, index) => {
      const isLast = index === visibleNodes.length - 1;
      if (ancestorsExpanded) {
        rows.push(toSpanRowView(node, depth, isLast, lineGuideLevel));
      }
      const expanded = options.expandedSpanIds.has(node.span.span_id);
      if (node.children.length) {
        const kind = resolveSpanKind(node.span);
        const childLineGuideLevel =
          depth > 0 && kind === 'AGENT' ? lineGuideLevel + 1 : lineGuideLevel;
        walk(node.children, depth + 1, ancestorsExpanded && expanded, childLineGuideLevel);
      }
    });
  };

  walk(trees, 0, true, 0);
  return rows;
}

/** API 字段名为 childs（非 children） */
function* walkSpans(nodes: LlmFlowSpan[]): Generator<LlmFlowSpan> {
  for (const node of nodes || []) {
    yield node;
    if (node.childs?.length) yield* walkSpans(node.childs);
  }
}

function toTree(nodes: LlmFlowSpan[]): SpanTreeNode[] {
  return (nodes || []).map(span => ({
    span,
    children: toTree(span.childs || []),
  }));
}

/** Agent 行角标：直接 + 间接子 Span 数量 */
function countDescendants(node: SpanTreeNode): number {
  return node.children.reduce((total, child) => total + 1 + countDescendants(child), 0);
}

/** 节点自身或任一后代命中筛选/关键字时保留，以便祖先链仍可见 */
function nodeMatchesOrHasMatch(node: SpanTreeNode, filter: LlmExecutionFilter, keyword: string): boolean {
  if (spanMatches(node.span, filter, keyword)) return true;
  return node.children.some(child => nodeMatchesOrHasMatch(child, filter, keyword));
}

/** 关键字匹配 span 标识、展示名、attributes 序列化文本 */
function spanMatches(span: LlmFlowSpan, filter: LlmExecutionFilter, keyword: string): boolean {
  const kind = resolveSpanKind(span);
  if (filter === 'error' && !isErrorSpan(span)) return false;
  if (filter === 'agent' && kind !== 'AGENT') return false;
  if (filter === 'llm' && kind !== 'LLM') return false;
  if (filter === 'tool' && kind !== 'TOOL') return false;
  if (!keyword) return true;
  const haystack = [
    span.span_id,
    span.span_name,
    pickSpanName(span),
    pickSpanSubtitle(span),
    stringifyContent(span.attributes),
  ]
    .join(' ')
    .toLowerCase();
  return haystack.includes(keyword);
}

/** LlmFlowSpan → 表格行视图；lineGuideLevel 供 span-row 绘制关系竖线 */
function toSpanRowView(
  node: SpanTreeNode,
  depth: number,
  isLast: boolean,
  lineGuideLevel: number
): LlmSpanRowView {
  const span = node.span;
  const attrs = span.attributes || {};
  const kind = resolveSpanKind(span);
  return {
    spanId: span.span_id,
    traceId: span.trace_id,
    kind,
    name: pickSpanName(span, kind),
    subtitle: pickSpanSubtitle(span, kind),
    description: pickDescription(span, kind),
    childCount: countDescendants(node),
    startTime: span.start_time,
    elapsedTime: span.elapsed_time,
    inputTokens: pickNumber(attrs, INPUT_TOKEN_KEYS),
    outputTokens: pickNumber(attrs, OUTPUT_TOKEN_KEYS),
    isError: isErrorSpan(span),
    errorMessage: String(span.status?.message || '').trim(),
    depth,
    hasChildren: node.children.length > 0,
    isLast,
    lineGuideLevel,
    io: pickIoPreview(span, kind),
    attributes: attrs,
    rawSpan: toRawSpan(span),
  };
}

function pickDescription(span: LlmFlowSpan, kind = resolveSpanKind(span)): string {
  const attrs = span.attributes || {};
  if (kind === 'AGENT') {
    return stringifyContent(getByPath(attrs, 'gen_ai.agent.description')).trim();
  }
  if (kind === 'TOOL') {
    return parseToolObservation(attrs).description;
  }
  return '';
}

/** Tool 用 KV 预览；LLM/Agent 取 parse-input/output 最后一条可读文本 */
function pickIoPreview(span: LlmFlowSpan, kind = resolveSpanKind(span)): LlmIoPreview {
  const attrs = span.attributes || {};
  if (kind === 'TOOL') {
    const tool = parseToolObservation(attrs);
    return {
      type: 'kv',
      input: flattenKvPairs(tool.arguments),
      output: flattenKvPairs(tool.result),
    };
  }
  const input = parseInputObservation(attrs);
  const output = parseOutputObservation(attrs);
  const inputText =
    input.userMessages.at(-1)?.content ||
    input.modelMessages.at(-1)?.content ||
    input.systemPrompts.at(-1)?.content ||
    '';
  const outputText = output.modelOutputs.at(-1)?.content || output.reasoningMessages.at(-1)?.content || '';
  return {
    type: 'text',
    input: inputText,
    output: outputText,
  };
}

/** 展示名：Tool/Agent 优先 gen_ai.*.name，LLM 用 span_name */
function pickSpanName(span: LlmFlowSpan, kind = resolveSpanKind(span)): string {
  const attrs = span.attributes || {};
  if (kind === 'TOOL') {
    return String(getByPath(attrs, 'gen_ai.tool.name') || span.span_name || '').trim();
  }
  if (kind === 'AGENT') {
    return String(getByPath(attrs, 'gen_ai.agent.name') || span.span_name || '').trim();
  }
  return span.span_name || '';
}

/** LLM 行副标题为 request/response model；Tool 固定 tool */
function pickSpanSubtitle(span: LlmFlowSpan, kind = resolveSpanKind(span)): string {
  const attrs = span.attributes || {};
  if (kind === 'LLM') {
    return String(getByPath(attrs, 'gen_ai.response.model') || getByPath(attrs, 'gen_ai.request.model') || '').trim();
  }
  if (kind === 'TOOL') return 'tool';
  return '';
}

/** Trace 卡片标题：首个有用户输入预览的 Span，否则根 span_name */
function pickTraceTitle(flow: LlmFlowSpan[]): string {
  for (const span of walkSpans(flow)) {
    const preview = pickIoPreview(span);
    if (preview.type === 'text' && preview.input.trim()) return preview.input.trim();
  }
  return flow[0]?.span_name || '';
}

/** 展开面板「原始 JSON」不含子树，避免体积过大 */
function toRawSpan(span: LlmFlowSpan): Record<string, unknown> {
  const { childs: _childs, ...rest } = span;
  return rest;
}
