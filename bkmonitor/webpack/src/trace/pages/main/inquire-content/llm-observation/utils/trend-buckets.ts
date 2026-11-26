import { collectSpanList, isErrorSpan, pickSpanTokenUsage, resolveSpanKind } from './transform';

import type { LlmExecutionFilter, LlmFlowSpan } from './typings';

/** 单根柱子的最小宽度（像素），用于按容器宽度推导桶数上限 */
export const MIN_BUCKET_WIDTH = 10;
/** 相邻柱子之间的间隔（像素） */
export const BUCKET_GAP = 1;

/** 趋势图序列键：耗时 / 总 Token */
export type LlmTrendSeriesKey = 'duration' | 'token';

/** 序列可见性，由图例「只看」控制 */
export type LlmTrendVisible = Record<LlmTrendSeriesKey, boolean>;

/**
 * 桶内多 Span 的聚合方式：
 * `sum` 取桶内所有 Span 之和，`max` 取桶内单个 Span 的最大值（默认）。
 */
export type LlmTrendAggregate = 'sum' | 'max';

/** 默认聚合方式：柱高取桶内最大单个 Span，而非多个 Span 之和 */
export const DEFAULT_TREND_AGGREGATE: LlmTrendAggregate = 'max';

/** 趋势图框选后的时间范围（微秒），null 表示未框选 */
export type LlmTrendTimeRange = [number, number];

/** 单个时间桶聚合结果：桶对应时间段（微秒）与桶内非 Agent Span 的耗时 / 总 Token */
export interface LlmTrendBucket {
  /** 桶内非 Agent Span 耗时（按聚合方式取和或最大值，微秒） */
  duration: number;
  /** 桶结束时间（微秒），与下一桶起始时间相接，构成连续时间段 [time, endTime)
   *  末桶对齐最晚起始时间，保证时间轴最右侧始终落在最后一个 Span 上 */
  endTime: number;
  /** 桶起始时间（微秒） */
  time: number;
  /** 桶内非 Agent Span 总 Token（按聚合方式取和或最大值） */
  tokens: number;
}

/** 按聚合方式合并桶内数值；初始值取 0，`max` 取最大、`sum` 累加 */
function aggregateBucketValue(current: number, value: number, mode: LlmTrendAggregate): number {
  return mode === 'max' ? Math.max(current, value) : current + value;
}

/** 收集 flow 中的非 Agent Span（Agent 为容器节点，耗时 / Token 由其子 Span 承担） */
export function pickTrendSpans(nodes: LlmFlowSpan[]): LlmFlowSpan[] {
  // 先深度优先展平，再剔除 Agent 容器节点，避免耗时 / Token 被父子重复统计
  return collectSpanList(nodes).filter(span => resolveSpanKind(span) !== 'AGENT');
}

/**
 * 按工具栏类型 Tab 从趋势图基座 Span 中再过滤，使趋势图随 Tab 联动。
 * 基座已排除 Agent 容器节点，故 `agent` 无独立数据；`all` 保持全部叶子 Span。
 */
export function pickTrendSpansByFilter(spans: LlmFlowSpan[], filter: LlmExecutionFilter): LlmFlowSpan[] {
  if (filter === 'all') return spans;
  if (filter === 'llm') return spans.filter(span => resolveSpanKind(span) === 'LLM');
  if (filter === 'tool') return spans.filter(span => resolveSpanKind(span) === 'TOOL');
  if (filter === 'error') return spans.filter(span => isErrorSpan(span));
  return [];
}

/**
 * 按容器宽度动态计算桶数：单根柱子最小 10px 且相邻柱间隔 1px，
 * 即单桶至少占用 11px。桶数不超过参与统计的 Span 数；桶宽随宽度浮动，
 * 保证柱宽不小于 10px。
 * @param plotWidth 绘图区宽度（不含 Y 轴标签区），未测量时为 0
 * @param spanCount 参与统计的非 Agent Span 数
 */
export function resolveBucketCount(plotWidth: number, spanCount: number): number {
  if (spanCount <= 0) return 0;
  const capacity = plotWidth > 0 ? Math.floor(plotWidth / (MIN_BUCKET_WIDTH + BUCKET_GAP)) : 0;
  const count = capacity > 0 ? Math.min(capacity, spanCount) : spanCount;
  return Math.max(1, count);
}

/**
 * 取起始时间落在桶时间段 [time, endTime) 内的 Span；
 * 最后一桶包含右端点，避免落在图表最大时间戳上的 Span 丢失。
 */
export function pickBucketSpans(spans: LlmFlowSpan[], bucket: LlmTrendBucket, isLast = false): LlmFlowSpan[] {
  if (!bucket) return [];
  return spans.filter(
    span =>
      span.start_time >= bucket.time && (isLast ? span.start_time <= bucket.endTime : span.start_time < bucket.endTime)
  );
}

/**
 * 剪掉每个 Span 的 childs（浅拷贝，不改动原树）。
 * 趋势图已将树展平为「桶内非 Agent Span」列表，统计面板内部还会按 childs 递归 collectSpanList，
 * 若不剪枝会导致同桶子孙被重复统计、且挂在桶内节点下却起始时间不在本桶的 Span 混入面板。
 */
export function stripSpanChilds(spans: LlmFlowSpan[]): LlmFlowSpan[] {
  return spans.map(span => ({ ...span, childs: [] }));
}

/** Span 起始时间是否落在框选时间范围内（闭区间）；范围为空时视为命中 */
export function isSpanInTimeRange(span: LlmFlowSpan, range: LlmTrendTimeRange | null): boolean {
  if (!range) return true;
  return span.start_time >= range[0] && span.start_time <= range[1];
}

/** 按框选时间范围过滤 Span；范围为空时原样返回，避免额外数组开销 */
export function filterSpansByTimeRange(spans: LlmFlowSpan[], range: LlmTrendTimeRange | null): LlmFlowSpan[] {
  if (!range) return spans;
  return spans.filter(span => isSpanInTimeRange(span, range));
}

/**
 * 将 ECharts 分类轴框选返回的下标区间换算成微秒时间范围：
 * 左端取起始桶起点、右端取结束桶终点，保证边界上的 Span 不被裁掉。
 */
export function resolveBucketTimeRange(buckets: LlmTrendBucket[], coordRange?: number[]): LlmTrendTimeRange | null {
  if (!coordRange?.length || !buckets.length) return null;
  const start = Math.min(coordRange[0], coordRange[1]);
  const end = Math.max(coordRange[0], coordRange[1]);
  const lo = Math.max(0, Math.min(buckets.length - 1, Math.floor(start)));
  const hi = Math.max(0, Math.min(buckets.length - 1, Math.ceil(end)));
  return [buckets[lo].time, buckets[hi].endTime];
}

/**
 * 将 Span 按时间等分桶并聚合耗时 / 总 Token；每个桶对应一个连续时间段，
 * 空桶保留以保证时间轴连续。Span 数超过容量时时间段聚合，否则每桶平均约 1 个 Span。
 * @param aggregate 桶内多 Span 的聚合方式，默认取最大值
 */
export function buildTrendBuckets(
  spans: LlmFlowSpan[],
  bucketCount: number,
  aggregate: LlmTrendAggregate = DEFAULT_TREND_AGGREGATE
): LlmTrendBucket[] {
  if (!spans.length || bucketCount <= 0) return [];
  // 时间轴范围取所有 Span 的 [最早起始, 最晚起始]：柱子按起始时间落点，右端必须对齐最后一个
  // Span 的起始时间。若改用最晚结束时间，单个长耗时 Span 会把轴尾拖到远超最后一个起始点，
  // 导致数据挤在左侧、右侧大段空桶。
  let min = Number.POSITIVE_INFINITY;
  let max = Number.NEGATIVE_INFINITY;
  for (const span of spans) {
    if (span.start_time < min) min = span.start_time;
    if (span.start_time > max) max = span.start_time;
  }
  if (!Number.isFinite(min) || !Number.isFinite(max)) return [];

  // 时间跨度（微秒）即最大可用桶数：桶宽 = 跨度 / 桶数，桶数超过跨度会让桶宽 < 1µs，
  // 遭 size 下限夹取后大量起始点会挤进末桶，故按跨度封顶。
  const timeSpan = max - min;
  if (timeSpan <= 0) {
    // 所有 Span 起始时间相同：收缩为单桶，时间轴与最后一个 Span 对齐
    return [
      {
        time: min,
        endTime: max,
        duration: spans.reduce(
          (acc, item) => aggregateBucketValue(acc, Math.max(0, item.elapsed_time || 0), aggregate),
          0
        ),
        tokens: spans.reduce((acc, item) => aggregateBucketValue(acc, pickSpanTokenUsage(item).total, aggregate), 0),
      },
    ];
  }
  const count = Math.max(1, Math.min(bucketCount, spans.length, Math.floor(timeSpan)));
  const size = timeSpan / count;
  // 桶宽 = 时间跨度 / 桶数；末桶右端点强制对齐 max，消除浮点累积误差
  const buckets: LlmTrendBucket[] = Array.from({ length: count }, (_, index) => ({
    time: min + index * size,
    endTime: index === count - 1 ? max : min + (index + 1) * size,
    duration: 0,
    tokens: 0,
  }));
  for (const span of spans) {
    // 按 Span 起始时间定位桶下标，并夹取到 [0, count-1] 防止越界
    const index = Math.min(count - 1, Math.max(0, Math.floor((span.start_time - min) / size)));
    buckets[index].duration = aggregateBucketValue(
      buckets[index].duration,
      Math.max(0, span.elapsed_time || 0),
      aggregate
    );
    buckets[index].tokens = aggregateBucketValue(buckets[index].tokens, pickSpanTokenUsage(span).total, aggregate);
  }
  return buckets;
}
