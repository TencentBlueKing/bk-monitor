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
import type { ModelConfig } from '@antv/g6';

// 节点概览页类型切换tab，linkedEdge-关联边，metric-指标
export type ActiveTab = 'linkedEdge' | 'metric';

// 事件分析弹窗列配置
export interface EventColumnConfig {
  alias: string;
  list: EventColumnItem[];
  name: string;
}

export interface EventColumnItem {
  alias: string;
  count: number;
  value: string;
}

// 事件分析弹窗选中数据配置
export interface EventConfig {
  [key: string]: EventConfigItem;
}
export interface EventSeries {
  alias?: string;
  datapoints: Array<[number, number]>;
  dimensions?: Record<string, any>;
  dimensions_translation?: Record<string, any>;
  metric_field?: string;
  target?: string;
  type?: string;
  unit?: string;
}

export interface EventStatistics {
  event_level: Record<string, number>;
  event_source: Record<string, number>;
}

export interface IEdge {
  [key: string]: any;
  edge_type: string;
  events: Record<string, any>[];
  is_anomaly: boolean;
}

export interface IEntity {
  aggregated_entites: IEntity[];
  alert_all_recorved: boolean;
  anomaly_score: number;
  anomaly_type: string;
  component_type?: string;
  dimensions: Record<string, any>;
  entity_id: string;
  entity_name: string;
  entity_type: string;
  is_anomaly: boolean;
  is_feedback_root: boolean;
  is_on_alert: boolean;
  is_root: boolean;
  properties?: Record<string, any>;
  rank: IRank;
  rank_name?: string;
  observe_time_rage?: {
    end_at: number | string;
    start_at: number | string;
  };
  rca_trace_info?: {
    abnormal_message: string;
    abnormal_traces: Record<string, any>[];
    abnormal_traces_query: Record<string, any>;
  };
  tags?: {
    BcsService?: IEntityTag;
    BcsWorkload?: IEntityTag;
  };
}

export interface IEntityTag {
  cluster_id: string;
  name: string;
  namespace: string;
}

// 事件详情菜单项
export interface IEventTagsItem {
  bk_biz_id: number | string;
  end_time: number; // 故障结束时间/当前时间
  index_info: Record<string, any>;
  interval: number;
  start_time: number; // 当前点击的事件的时间戳
}

export interface IMetricItem {
  display_by_dimensions: boolean; // 是否为多维度指标
  metric_alias: string;
  metric_name: string;
  metric_type: string;
  time_series: Record<string, ITimeSeries>;
}

export interface IncidentDetailData {
  begin_time?: number;
  bk_biz_id: string;
  create_time: number;
  current_snapshot?: any;
  end_time: number;
  id: string;
  incident_id: string;
}

export interface IPosition {
  left: number;
  top: number;
}

export interface IRank {
  anomaly_count: number;
  is_sub_rank: boolean;
  nodes: ITopoNode[];
  rank_alias: string;
  rank_id: number;
  rank_name: string;
  total: number;
  rank_category: {
    category_alias: string;
    category_id: number;
    category_name: string;
  };
}

export interface ITimeSeries {
  [key: string]: any;
  datapoints: Array<[number, number, number]>; // 指标数据
  unit: string;
}

export interface ITopoCombo extends ModelConfig {
  [key: string]: any;
  dataType?: string;
  id: number | string;
  label?: string;
}

export interface ITopoData {
  combos: ITopoCombo[];
  edges: IEdge[];
  nodes: ITopoNode[];
}

export interface ITopoEdge extends ModelConfig {
  aggregated: boolean;
  count: number;
  source: string;
  target: string;
  type: 'dependency' | 'invoke';
}

export interface ITopoNode extends ModelConfig {
  aggregated_nodes?: ITopoNode[];
  alert_ids?: string[];
  bk_biz_id?: string;
  bk_biz_name?: string;
  comboId?: string;
  entity?: IEntity;
  id?: string;
  is_deleted?: boolean;
  is_feedback_root?: boolean;
  node?: any;
  originComboId?: string;
  subComboId?: string;
  alert_display?: {
    alert_id: string;
    alert_name: string;
  };
  properties: {
    aggregated_by?: string[];
  };
}

// 事件数据，用于构造散点图
export interface MetricEvent {
  event_alias?: string;
  event_level: string;
  event_name: string;
  event_source: string;
  series: EventSeries[];
}

export interface TopoRawData {
  content: ITopoData[];
  create_time: number;
  fpp_snapshot_id: string;
  incident_id: string;
}

interface EventConfigItem {
  is_select_all: boolean;
  list: string[];
}
