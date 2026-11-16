import { collectSpanList, flattenVisibleSpanRows, isErrorSpan, pickSpanName, resolveSpanKind } from './transform';

import type { LlmFlowSpan, LlmSpanKind, LlmSpanRowView } from './typings';

export type DurationRankMode = 'bottom' | 'top';

export interface DurationGroupStat {
  avg: number;
  count: number;
  errorCount: number;
  key: string;
  name: string;
  p50: number;
  p95: number;
  total: number;
}

export interface DurationSpanStat {
  elapsedTime: number;
  name: string;
  percent: number;
  spanId: string;
  startTime: number;
}

const FALLBACK_NAME = '--';

/** nearest-rank：P50 / P95，样本为空时返回 0 */
export function calcPercentile(values: number[], percentile: number): number {
  if (!values.length) return 0;
  const sorted = [...values].sort((left, right) => left - right);
  const index = Math.min(sorted.length - 1, Math.max(0, Math.ceil((percentile / 100) * sorted.length) - 1));
  return sorted[index];
}

/** 收集目标 Span 的祖先 id，定位前展开子树用 */
export function collectAncestorSpanIds(nodes: LlmFlowSpan[], spanId: string): string[] {
  const walk = (items: LlmFlowSpan[], ancestors: string[]): string[] | null => {
    for (const item of items || []) {
      if (item.span_id === spanId) return ancestors;
      const found = walk(item.childs || [], [...ancestors, item.span_id]);
      if (found) return found;
    }
    return null;
  };
  return walk(nodes, []) || [];
}

/** 按名称聚合当前类型 Span：次数、异常、分位和平均耗时 */
export function buildDurationGroupStats(flow: LlmFlowSpan[], kind: LlmSpanKind): DurationGroupStat[] {
  const groups = new Map<string, { durations: number[]; errorCount: number; name: string }>();

  for (const span of collectKindSpans(flow, kind)) {
    const name = pickSpanName(span, kind) || span.span_name || FALLBACK_NAME;
    const current = groups.get(name) || { durations: [], errorCount: 0, name };
    current.durations.push(Math.max(0, span.elapsed_time || 0));
    if (isErrorSpan(span)) current.errorCount += 1;
    groups.set(name, current);
  }

  return [...groups.values()]
    .map(group => {
      const total = group.durations.reduce((sum, value) => sum + value, 0);
      return {
        key: group.name,
        name: group.name,
        count: group.durations.length,
        errorCount: group.errorCount,
        p50: calcPercentile(group.durations, 50),
        p95: calcPercentile(group.durations, 95),
        avg: group.durations.length ? total / group.durations.length : 0,
        total,
      };
    })
    .sort((left, right) => right.total - left.total);
}

/** 当前类型 Span 列表，占比相对该类耗时之和；再按 Top / Bottom 截断 */
export function buildDurationSpanStats(
  flow: LlmFlowSpan[],
  kind: LlmSpanKind,
  rankMode: DurationRankMode
): DurationSpanStat[] {
  const items = collectKindSpans(flow, kind).map(span => ({
    spanId: span.span_id,
    name: pickSpanName(span, kind) || span.span_name || FALLBACK_NAME,
    startTime: span.start_time,
    elapsedTime: Math.max(0, span.elapsed_time || 0),
    percent: 0,
  }));
  const total = items.reduce((sum, item) => sum + item.elapsedTime, 0);
  for (const item of items) {
    item.percent = total > 0 ? (item.elapsedTime / total) * 100 : 0;
  }
  items.sort((left, right) =>
    rankMode === 'top' ? right.elapsedTime - left.elapsedTime : left.elapsedTime - right.elapsedTime
  );
  return items.slice(0, 10);
}

/** 展开全部节点后按 spanId 取行，供详情侧栏复用现有 LlmSpanRowView */
export function findSpanRowView(flow: LlmFlowSpan[], spanId: string): LlmSpanRowView | undefined {
  const expandedSpanIds = new Set(collectSpanList(flow).map(span => span.span_id));
  return flattenVisibleSpanRows(flow, {
    expandedSpanIds,
    filter: 'all',
    keyword: '',
  }).find(row => row.spanId === spanId);
}

function collectKindSpans(flow: LlmFlowSpan[], kind: LlmSpanKind): LlmFlowSpan[] {
  return collectSpanList(flow).filter(span => resolveSpanKind(span) === kind);
}
