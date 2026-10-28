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
/** 旧版 Profiling 的 `target` 查询参数，转换成新版 `profiling` 快照。 */

const RESERVED_LABELS = new Set(['start', 'end', '__proto__', 'constructor', 'prototype']);

const GRAPH_MODES = {
  combine: 'combined',
  combined: 'combined',
  flame: 'flame',
  flamegraph: 'flame',
  table: 'table',
  topo: 'callgraph',
  callgraph: 'callgraph',
} as const;

export interface ProfilingExploreState {
  aggregation?: Aggregation;
  appName?: string;
  baselineRange?: [number, number];
  comparisonRange?: [number, number];
  comparisonWhere?: ProfilingWhere[];
  dataType?: string;
  mode?: CompareMode;
  serviceName?: string;
  timeRange?: [TimePoint, TimePoint];
  where?: ProfilingWhere[];
  file?: {
    aggregation?: Aggregation;
    dataType?: string;
    pendingTimeRange?: boolean;
    profileId: string;
    view?: {
      graphMode?: GraphMode;
    };
    where?: ProfilingWhere[];
  };
  view?: {
    graphMode?: GraphMode;
    tab?: 'file';
  };
}
type Aggregation = 'AVG' | 'LAST' | 'SUM';
type CompareMode = 'condition' | 'none' | 'time';
type GraphMode = (typeof GRAPH_MODES)[keyof typeof GRAPH_MODES];

interface ProfilingWhere {
  key: string;
  method: 'equal';
  value: Array<number | string>;
}

type TimePoint = number | string;

export const PROFILING_EXPLORE_PATH = '/trace/profiling-explore';

const isRecord = (value: unknown): value is Record<string, unknown> =>
  !!value && typeof value === 'object' && !Array.isArray(value);

const readLegacyTarget = (input: unknown): null | Record<string, unknown> => {
  const value = Array.isArray(input) ? input[0] : input;
  if (isRecord(value)) return value;
  if (typeof value !== 'string' || !value.trim()) return null;
  let text = value.trim();
  for (let i = 0; i < 2; i++) {
    try {
      const parsed = JSON.parse(text);
      if (isRecord(parsed)) return parsed;
    } catch {
      // 旧链接先做了 encodeURIComponent，路由解一次后可能仍是编码字符串。
    }
    try {
      const decoded = decodeURIComponent(text);
      if (decoded === text) break;
      text = decoded;
    } catch {
      break;
    }
  }
  return null;
};

/** 秒、毫秒、微秒都收成毫秒。旧图表把时间选区放在标签里，单位是微秒。 */
const toEpochMs = (value: unknown): number | undefined => {
  const numeric =
    typeof value === 'number'
      ? value
      : typeof value === 'string' && /^\d+(\.\d+)?$/.test(value.trim())
        ? Number(value.trim())
        : Number.NaN;
  if (!Number.isFinite(numeric) || numeric < 1e9) return undefined;
  if (numeric >= 1e14) return Math.trunc(numeric / 1000);
  if (numeric >= 1e11) return Math.trunc(numeric);
  return Math.trunc(numeric * 1000);
};

const toTimePoint = (value: unknown): TimePoint | undefined => {
  if (typeof value === 'number') return toEpochMs(value);
  if (typeof value !== 'string') return undefined;
  const text = value.trim();
  if (!text) return undefined;
  return toEpochMs(text) ?? text;
};

const toTimeRange = (start: unknown, end: unknown): [TimePoint, TimePoint] | undefined => {
  const left = toTimePoint(start);
  const right = toTimePoint(end);
  if (left == null || right == null) return undefined;
  if (typeof left === 'number' && typeof right === 'number' && right <= left) return undefined;
  return [left, right];
};

const toSelection = (labels: unknown): [number, number] | undefined => {
  if (!isRecord(labels)) return undefined;
  const start = toEpochMs(labels.start);
  const end = toEpochMs(labels.end);
  if (start == null || end == null || end <= start) return undefined;
  return [start, end];
};

const toLabelValues = (value: unknown): Array<number | string> => {
  const list = Array.isArray(value) ? value : [value];
  return list.filter((item): item is number | string => {
    if (typeof item === 'number') return Number.isFinite(item);
    return typeof item === 'string' && item !== '';
  });
};

/** start/end 是时间选区保留字段，不能当成标签，否则新版查询会直接失败。 */
const toWhere = (labels: unknown): ProfilingWhere[] => {
  if (!isRecord(labels)) return [];
  const where: ProfilingWhere[] = [];
  for (const [key, value] of Object.entries(labels)) {
    if (!key || RESERVED_LABELS.has(key)) continue;
    const values = toLabelValues(value);
    if (!values.length) continue;
    where.push({ key, method: 'equal', value: values });
  }
  return where;
};

const toAggregation = (value: unknown): Aggregation | undefined =>
  value === 'AVG' || value === 'SUM' || value === 'LAST' ? value : undefined;

const toGraphMode = (value: unknown): GraphMode | undefined => {
  const list = Array.isArray(value) ? value : [value];
  for (const item of list) {
    if (typeof item !== 'string') continue;
    const mode = GRAPH_MODES[item.toLowerCase()];
    if (mode) return mode;
  }
  return undefined;
};

const text = (value: unknown) => (typeof value === 'string' ? value.trim() : '');

const isCompared = (value: unknown) => value === true || value === 1 || value === 'true';

export function adaptLegacyProfilingTarget(input: unknown): null | ProfilingExploreState {
  const target = readLegacyTarget(input);
  if (!target) return null;
  const appName = text(target.app_name);
  const serviceName = text(target.service_name);
  const dataType = text(target.data_type);
  const aggregation = toAggregation(target.agg_method);
  const profileId = text(target.profile_id);
  const timeRange = toTimeRange(target.start, target.end);
  const where = toWhere(target.filter_labels);
  const comparisonWhere = toWhere(target.diff_filter_labels);
  const useFile = !!profileId && !appName;
  if (useFile) {
    const graphMode = toGraphMode(target.diagram_types);
    return {
      ...(timeRange ? { timeRange } : {}),
      view: { tab: 'file' },
      file: {
        profileId,
        ...(dataType ? { dataType } : {}),
        ...(aggregation ? { aggregation } : {}),
        ...(where.length ? { where } : {}),
        ...(!timeRange ? { pendingTimeRange: true } : {}),
        ...(graphMode ? { view: { graphMode } } : {}),
      },
    };
  }

  const baselineRange = toSelection(target.filter_labels);
  const comparisonRange = toSelection(target.diff_filter_labels);
  let mode: CompareMode = 'none';
  if (baselineRange && comparisonRange) mode = 'time';
  else if (isCompared(target.is_compared) || comparisonWhere.length) mode = 'condition';
  let graphMode = toGraphMode(target.diagram_types);
  // 新版对比模式不支持调用图，恢复时也会落回合并视图。
  if (graphMode === 'callgraph' && mode !== 'none') graphMode = 'combined';

  const state: ProfilingExploreState = {
    ...(appName ? { appName } : {}),
    ...(serviceName ? { serviceName } : {}),
    ...(dataType ? { dataType } : {}),
    ...(aggregation ? { aggregation } : {}),
    ...(timeRange ? { timeRange } : {}),
    ...(where.length ? { where } : {}),
    ...(comparisonWhere.length ? { comparisonWhere } : {}),
    ...(mode !== 'none' ? { mode } : {}),
    ...(mode === 'time' && baselineRange && comparisonRange ? { baselineRange, comparisonRange } : {}),
    ...(graphMode ? { view: { graphMode } } : {}),
  };
  return Object.keys(state).length ? state : null;
}

export function buildProfilingExploreLocation(target?: unknown) {
  const state = adaptLegacyProfilingTarget(target);
  const query: Record<string, string> = {};
  if (state) query.profiling = JSON.stringify(state);
  return { path: PROFILING_EXPLORE_PATH, query };
}

export function profilingExploreHash(target?: unknown) {
  const { path, query } = buildProfilingExploreLocation(target);
  if (!query.profiling) return `#${path}`;
  return `#${path}?profiling=${encodeURIComponent(query.profiling)}`;
}
