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

import type { FileQueryState } from './file';
import type { IWhereItem } from '@/components/retrieval-filter/typing';

export type Aggregation = 'AVG' | 'LAST' | 'SUM';
export interface Application {
  app_alias: string;
  app_name: string;
  application_id?: number;
  description?: string;
  has_data?: boolean;
  services: { name: string }[];
}
export type CompareMode = 'condition' | 'none' | 'time';
export interface DiffInfo {
  baseline: number;
  comparison: number;
  /** 后端返回比例值（0.25 表示 25%）；新增/移除优先按 mark 展示。 */
  diff: null | number;
  mark: 'added' | 'changed' | 'removed' | 'unchanged';
}
export interface FlameNode {
  children?: FlameNode[];
  diff_info?: DiffInfo;
  id: number | string;
  name: string;
  self?: number;
  value: number;
}
export type GraphMode = 'callgraph' | 'combined' | 'flame' | 'table';
export type ProfileQuery = ProfileQueryBase &
  (
    | { app_name: string; global_query?: false; profile_id?: never; service_name: string }
    | { app_name?: never; global_query: true; profile_id: string; service_name?: never }
  );

export interface ProfileResult {
  call_graph_data?: string;
  flame_data?: FlameNode;
  table_data?: { baseline_total?: number; comparison_total?: number; items: ProfileRow[]; total: number };
  unit?: string;
}

export interface ProfileRow extends Partial<DiffInfo> {
  id: number | string;
  name: string;
  self: number;
  total?: number;
  value?: number;
}

export interface ProfileSeries {
  alias?: string;
  /** 接口点位顺序为 [数值, 毫秒时间戳]，与 ECharts 时间轴需要的顺序相反。 */
  datapoints: [null | number, number][];
  dimensions?: Record<string, string>;
  target: string;
  trace_data?: Record<string, { span_id: string; time: string }[]>;
  unit: string;
}

/** 可分享的展示状态；悬浮提示、菜单开关等瞬态交互不进入快照。 */
export interface ProfileViewState {
  callGraph: { scale: number; x: number; y: number };
  direction: 'ltr' | 'rtl';
  flameFocus: string[];
  graphMode: GraphMode;
  highlight: string;
  keyword: string;
  legend: Record<string, boolean>;
  sort: { descending: boolean; sortBy: string };
  tab: ProfilingTab;
  traceMode: boolean;
  trendCollapsed: boolean;
}

export interface ProfilingFavorite {
  config: ProfilingFavoriteConfig;
  id: number;
  name: string;
}

export interface ProfilingFavoriteConfig {
  bk_biz_id: number;
  profiling: QueryState;
  version: 1;
}

export type ProfilingTab = 'application' | 'collection' | 'file';

export type QuerySide = 'baseline' | 'comparison';

export interface QueryState {
  aggregation: Aggregation;
  appName: string;
  baselineRange: null | SelectionRange;
  commonWhere: IWhereItem[];
  comparisonCommonWhere: IWhereItem[];
  comparisonRange: null | SelectionRange;
  comparisonWhere: IWhereItem[];
  dataType: string;
  file: FileQueryState;
  mode: CompareMode;
  refreshInterval: number;
  /** 上次查询的绝对毫秒边界，用于固定 URL 现场及平移相对时间收藏中的选区。 */
  resolvedTimeRange: null | SelectionRange;
  serviceName: string;
  timeRange: TimeRange;
  timezone: string;
  view: ProfileViewState;
  where: IWhereItem[];
}

export type SelectionRange = [number, number];

export interface ServiceDetail {
  app_name: string;
  create_time: number;
  data_types: { default_agg_method: Aggregation; is_large?: boolean; key: string; name: string }[];
  last_report_time: null | number;
  name: string;
}

export type TimeRange = [number | string, number | string];

export interface TrendResult {
  series: ProfileSeries[];
}

interface ProfileQueryBase {
  agg_method: Aggregation;
  bk_biz_id: number;
  data_type: string;
  diagram_types?: string[];
  diff_filter_labels: Record<string, number | string | string[]>;
  end: number;
  filter_labels: Record<string, number | string | string[]>;
  is_compared: boolean;
  start: number;
}
