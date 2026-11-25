import { collectSpanList, pickSpanName, pickSpanTokenUsage, resolveSpanKind } from './transform';

import type { LlmFlowSpan } from './typings';

export type TokenMetric = 'cacheRead' | 'cacheWrite' | 'input' | 'output' | 'total';

export type TokenRankMode = 'bottom' | 'top';

export interface TokenSpanStat {
  name: string;
  percent: number;
  spanId: string;
  startTime: number;
  tokens: number;
}

const FALLBACK_NAME = '--';

/** 当前指标是否存在大于 0 的 Span，供面板按数据隐藏空 Tab */
export function hasTokenMetricData(flow: LlmFlowSpan[], metric: TokenMetric): boolean {
  return collectSpanList(flow)
    .filter(span => resolveSpanKind(span) !== 'AGENT')
    .some(span => (pickSpanTokenUsage(span)[metric] || 0) > 0);
}

/** 当前指标 > 0 的 Span，占比相对该类 Token 之和；再按 Top / Bottom 截断 */
export function buildTokenSpanStats(flow: LlmFlowSpan[], metric: TokenMetric, rankMode: TokenRankMode): TokenSpanStat[] {
  const items = collectSpanList(flow)
    .filter(span => resolveSpanKind(span) !== 'AGENT')
    .map(span => ({
      spanId: span.span_id,
      name: pickSpanName(span) || span.span_name || FALLBACK_NAME,
      startTime: span.start_time,
      tokens: Math.max(0, pickSpanTokenUsage(span)[metric] || 0),
      percent: 0,
    }))
    .filter(item => item.tokens > 0);
  const total = items.reduce((sum, item) => sum + item.tokens, 0);
  for (const item of items) {
    item.percent = total > 0 ? (item.tokens / total) * 100 : 0;
  }
  items.sort((left, right) => (rankMode === 'top' ? right.tokens - left.tokens : left.tokens - right.tokens));
  return items.slice(0, 10);
}
