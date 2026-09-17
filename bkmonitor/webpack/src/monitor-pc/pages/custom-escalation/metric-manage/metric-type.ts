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

/** Prometheus / 自定义指标类型 */
export type MetricTypeValue = 'unclassified' | 'gauge' | 'counter' | 'histogram' | 'summary';

/** 类型来源 */
export type MetricTypeSource = 'reported' | 'manual' | 'unrecognized';

/** 时序性 */
export type MetricTemporality = 'cumulative' | 'delta';

/** 指标族成员 */
export interface IMetricFamilyMember {
  field_id: number;
  name: string;
  suffix: string;
}

/** 指标类型相关扩展字段（后端就绪后由接口返回；前端缺失时用 Mock 补齐） */
export interface IMetricTypeMeta {
  /** 是否为聚合父指标（指标族） */
  is_family_parent?: boolean;
  /** 指标族名称（父指标名） */
  metric_family?: string;
  /** 真实成员（仅父指标） */
  family_members?: IMetricFamilyMember[];
  /** 指标类型 */
  metric_type?: MetricTypeValue;
  /** 类型来源 */
  type_source?: MetricTypeSource;
  /** 时序性，默认 cumulative */
  temporality?: MetricTemporality;
  /** 人工确认类型与自动识别冲突 */
  type_conflict?: boolean;
  /** 行是否可展开（有真实成员） */
  expandable?: boolean;
  /** 是否为 Mock 补齐数据 */
  __mock_type_meta?: boolean;
}

export const METRIC_TYPE_ALL = '__all_metric_type__';

export const METRIC_TYPE_OPTIONS: { id: MetricTypeValue | typeof METRIC_TYPE_ALL; name: string }[] = [
  { id: METRIC_TYPE_ALL, name: window.i18n.tc('全部') },
  { id: 'unclassified', name: window.i18n.tc('待分类') },
  { id: 'gauge', name: 'Gauge' },
  { id: 'counter', name: 'Counter' },
  { id: 'histogram', name: 'Histogram' },
  { id: 'summary', name: 'Summary' },
];

export const METRIC_TYPE_LABEL_MAP: Record<MetricTypeValue, string> = {
  unclassified: window.i18n.tc('待分类'),
  gauge: 'Gauge',
  counter: 'Counter',
  histogram: 'Histogram',
  summary: 'Summary',
};

export const METRIC_TYPE_SOURCE_LABEL_MAP: Record<MetricTypeSource, string> = {
  reported: window.i18n.tc('上报识别'),
  manual: window.i18n.tc('人工确认'),
  unrecognized: window.i18n.tc('未识别'),
};

export const METRIC_TEMPORALITY_OPTIONS: { id: MetricTemporality; name: string }[] = [
  { id: 'cumulative', name: window.i18n.tc('累计') },
  { id: 'delta', name: window.i18n.tc('增量') },
];

/** Histogram / Summary 常见成员后缀 */
const FAMILY_SUFFIXES = ['_bucket', '_sum', '_count', '_created'] as const;

const MOCK_TYPE_CYCLE: MetricTypeValue[] = ['gauge', 'counter', 'histogram', 'summary', 'unclassified'];

/**
 * 从指标名解析族名与后缀
 */
export function parseMetricFamilyName(name: string): { family: string; suffix: string } | null {
  for (const suffix of FAMILY_SUFFIXES) {
    if (name.endsWith(suffix) && name.length > suffix.length) {
      return { family: name.slice(0, -suffix.length), suffix };
    }
  }
  return null;
}

/**
 * 判断后端是否已返回类型元数据
 */
export function hasBackendMetricTypeMeta(item: IMetricTypeMeta): boolean {
  return Boolean(item?.metric_type) && !item.__mock_type_meta;
}

/**
 * 按名称启发式推断类型（Mock）
 */
function inferMockMetricType(name: string, index: number): {
  metric_type: MetricTypeValue;
  type_source: MetricTypeSource;
  temporality: MetricTemporality;
  type_conflict: boolean;
} {
  const lower = name.toLowerCase();
  if (parseMetricFamilyName(name)) {
    return {
      metric_type: lower.includes('quantile') || lower.includes('summary') ? 'summary' : 'histogram',
      type_source: 'reported',
      temporality: 'cumulative',
      type_conflict: false,
    };
  }
  if (/(_total|_count)$/i.test(name) || /counter/i.test(name)) {
    return {
      metric_type: 'counter',
      type_source: 'reported',
      temporality: 'cumulative',
      type_conflict: false,
    };
  }
  if (/(_gauge|usage|ratio|percent)$/i.test(name) || /gauge/i.test(name)) {
    return {
      metric_type: 'gauge',
      type_source: 'reported',
      temporality: 'delta',
      type_conflict: false,
    };
  }
  if (/pending|unknown|todo/i.test(name)) {
    return {
      metric_type: 'unclassified',
      type_source: 'unrecognized',
      temporality: 'cumulative',
      type_conflict: false,
    };
  }
  const metric_type = MOCK_TYPE_CYCLE[index % MOCK_TYPE_CYCLE.length];
  const type_source: MetricTypeSource =
    metric_type === 'unclassified' ? 'unrecognized' : index % 5 === 0 ? 'manual' : 'reported';
  return {
    metric_type,
    type_source,
    temporality: metric_type === 'counter' ? 'cumulative' : index % 3 === 0 ? 'delta' : 'cumulative',
    type_conflict: type_source === 'manual' && index % 7 === 0,
  };
}

type MetricListItem = {
  id: number;
  name: string;
  config: Record<string, any>;
  [key: string]: any;
} & IMetricTypeMeta;

/**
 * 为指标列表补齐类型元数据，并将 Histogram/Summary 成员收敛为可展开的聚合父指标
 * - 后端已有 metric_type 时优先使用，仅补齐缺失字段
 * - 否则按名称 Mock，并按后缀聚合指标族
 */
export function enrichAndCollapseMetricTypeList<T extends MetricListItem>(list: T[]): T[] {
  if (!list?.length) return [];

  const backendReady = list.some(item => hasBackendMetricTypeMeta(item));
  const enriched = list.map((item, index) => {
    if (item.metric_type) {
      return {
        ...item,
        type_source: item.type_source || 'reported',
        temporality: item.temporality || 'cumulative',
        type_conflict: Boolean(item.type_conflict),
        is_family_parent: Boolean(item.is_family_parent),
        expandable: Boolean(item.expandable || item.family_members?.length),
        __mock_type_meta: Boolean(item.__mock_type_meta),
      } as T;
    }
    const inferred = inferMockMetricType(item.name, index);
    const parsed = parseMetricFamilyName(item.name);
    return {
      ...item,
      ...inferred,
      metric_family: parsed?.family,
      is_family_parent: false,
      expandable: false,
      family_members: [],
      __mock_type_meta: true,
    } as T;
  });

  if (backendReady) {
    // 后端已返回类型时，仍把带 family_members 的父指标标记为可展开
    return enriched.map(item => ({
      ...item,
      expandable: Boolean(item.is_family_parent && item.family_members?.length),
    }));
  }

  // Mock：按族名聚合 _bucket/_sum/_count 等真实成员
  const familyMap = new Map<string, T[]>();
  const normals: T[] = [];

  for (const item of enriched) {
    const parsed = parseMetricFamilyName(item.name);
    if (!parsed) {
      normals.push(item);
      continue;
    }
    const bucket = familyMap.get(parsed.family) || [];
    bucket.push(item);
    familyMap.set(parsed.family, bucket);
  }

  const parents: T[] = [];
  for (const [family, members] of familyMap.entries()) {
    if (members.length < 2) {
      // 只有单个后缀成员时不造父指标，避免凭空生成不存在的成员
      normals.push(...members);
      continue;
    }
    const base = members[0];
    const metric_type: MetricTypeValue =
      members.some(m => m.name.endsWith('_bucket')) || base.metric_type === 'histogram' ? 'histogram' : 'summary';
    parents.push({
      ...base,
      id: base.id,
      name: family,
      metric_family: family,
      metric_type,
      type_source: 'reported',
      temporality: 'cumulative',
      type_conflict: false,
      is_family_parent: true,
      expandable: true,
      movable: false,
      family_members: members.map(m => {
        const parsed = parseMetricFamilyName(m.name);
        return {
          field_id: m.id,
          name: m.name,
          suffix: parsed?.suffix || '',
        };
      }),
      __mock_type_meta: true,
      // 保留原始成员，展开行渲染用
      __family_member_rows: members,
    } as T);
  }

  return [...parents, ...normals];
}

/**
 * 若列表中完全没有可收敛的指标族，注入一组演示用 Histogram 族数据，便于前端联调
 */
export function ensureDemoMetricFamilyIfNeeded<T extends MetricListItem>(list: T[]): T[] {
  if (!list?.length) return list;
  if (list.some(item => item.is_family_parent)) return list;

  const template = list[0];
  const demoIdBase = 900000 + (template.id % 1000);
  const family = 'http_request_duration_seconds';
  const members = ['_bucket', '_sum', '_count'].map((suffix, idx) => ({
    ...template,
    id: demoIdBase + idx + 1,
    name: `${family}${suffix}`,
    movable: true,
    metric_type: 'histogram' as MetricTypeValue,
    type_source: 'reported' as MetricTypeSource,
    temporality: 'cumulative' as MetricTemporality,
    type_conflict: false,
    is_family_parent: false,
    expandable: false,
    family_members: [],
    __mock_type_meta: true,
    selection: false,
  }));

  const parent = {
    ...template,
    id: demoIdBase,
    name: family,
    movable: false,
    metric_type: 'histogram' as MetricTypeValue,
    type_source: 'reported' as MetricTypeSource,
    temporality: 'cumulative' as MetricTemporality,
    type_conflict: false,
    is_family_parent: true,
    expandable: true,
    metric_family: family,
    family_members: members.map(m => ({
      field_id: m.id,
      name: m.name,
      suffix: m.name.slice(family.length),
    })),
    __family_member_rows: members,
    __mock_type_meta: true,
    selection: false,
  } as T;

  // 再造一条冲突样例，便于验证「处理」入口
  const conflictItem = {
    ...template,
    id: demoIdBase + 10,
    name: 'demo_manual_conflict_metric',
    metric_type: 'gauge' as MetricTypeValue,
    type_source: 'manual' as MetricTypeSource,
    temporality: 'cumulative' as MetricTemporality,
    type_conflict: true,
    is_family_parent: false,
    expandable: false,
    __mock_type_meta: true,
    selection: false,
  } as T;

  return [parent, conflictItem, ...list];
}

/**
 * 可视化指标树：将带后缀的成员收敛为聚合指标名，不展示子指标
 */
export function collapseMetricTreeMetrics<
  T extends { alias: string; field_id: number; metric_name: string; metric_type?: MetricTypeValue; is_family_parent?: boolean; family_members?: IMetricFamilyMember[] },
>(metrics: T[]): T[] {
  if (!metrics?.length) return [];
  const familyMap = new Map<string, T[]>();
  const normals: T[] = [];

  for (const item of metrics) {
    if (item.is_family_parent || item.metric_type === 'histogram' || item.metric_type === 'summary') {
      if (!parseMetricFamilyName(item.metric_name)) {
        normals.push({ ...item, is_family_parent: true, metric_type: item.metric_type || 'histogram' });
        continue;
      }
    }
    const parsed = parseMetricFamilyName(item.metric_name);
    if (!parsed) {
      const index = normals.length;
      const inferred = item.metric_type ? null : inferMockMetricType(item.metric_name, index);
      normals.push({
        ...item,
        metric_type: item.metric_type || inferred?.metric_type,
      });
      continue;
    }
    const bucket = familyMap.get(parsed.family) || [];
    bucket.push(item);
    familyMap.set(parsed.family, bucket);
  }

  const parents: T[] = [];
  for (const [family, members] of familyMap.entries()) {
    if (members.length < 2) {
      normals.push(...members.map(m => ({ ...m, metric_type: m.metric_type || 'histogram' })));
      continue;
    }
    const base = members[0];
    parents.push({
      ...base,
      metric_name: family,
      alias: base.alias || family,
      metric_type: 'histogram',
      is_family_parent: true,
      family_members: members.map(m => {
        const parsed = parseMetricFamilyName(m.metric_name);
        return { field_id: m.field_id, name: m.metric_name, suffix: parsed?.suffix || '' };
      }),
    });
  }

  return [...parents, ...normals];
}

/**
 * 可视化树：无 Histogram 族时注入演示聚合指标
 */
export function ensureDemoMetricTreeIfNeeded<
  T extends {
    alias: string;
    field_id: number;
    metric_name: string;
    metric_type?: MetricTypeValue;
    is_family_parent?: boolean;
    family_members?: IMetricFamilyMember[];
  },
>(metrics: T[]): T[] {
  const collapsed = collapseMetricTreeMetrics(metrics);
  if (collapsed.some(item => item.is_family_parent || item.metric_type === 'histogram')) {
    return collapsed;
  }
  if (!collapsed.length && !metrics.length) {
    return [
      {
        alias: 'http_request_duration_seconds',
        field_id: 900001,
        metric_name: 'http_request_duration_seconds',
        metric_type: 'histogram',
        is_family_parent: true,
        family_members: [
          { field_id: 900002, name: 'http_request_duration_seconds_bucket', suffix: '_bucket' },
          { field_id: 900003, name: 'http_request_duration_seconds_sum', suffix: '_sum' },
          { field_id: 900004, name: 'http_request_duration_seconds_count', suffix: '_count' },
        ],
      } as T,
    ];
  }
  if (!collapsed.length) return collapsed;
  const base = collapsed[0];
  return [
    {
      ...base,
      alias: 'http_request_duration_seconds',
      field_id: 900001,
      metric_name: 'http_request_duration_seconds',
      metric_type: 'histogram',
      is_family_parent: true,
    },
    ...collapsed,
  ];
}

export function getMetricTypeLabel(type?: MetricTypeValue) {
  return (type && METRIC_TYPE_LABEL_MAP[type]) || METRIC_TYPE_LABEL_MAP.unclassified;
}

export function getMetricTypeSourceLabel(source?: MetricTypeSource) {
  return (source && METRIC_TYPE_SOURCE_LABEL_MAP[source]) || METRIC_TYPE_SOURCE_LABEL_MAP.unrecognized;
}
