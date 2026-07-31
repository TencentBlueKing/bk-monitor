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

/**
 * @file 拓扑图业务类型声明
 * @description 定义拓扑图中节点、边、实体、指标、事件等业务数据结构
 */

import type { ModelConfig } from '@antv/g6';

/** 节点概览页类型切换tab，linkedEdge-关联边，metric-指标 */
export type ActiveTab = 'linkedEdge' | 'metric';

/** 事件分析弹窗列配置 */
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

/** 事件分析弹窗选中数据配置 */
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

/** 拓扑图边数据 */
export interface IEdge {
  [key: string]: any;
  aggregated?: boolean;
  aggregated_edges?: IEdge[];
  anomaly_score: number;
  count?: number;
  direction?: string;
  edge_type: string;
  events: Record<string, any>[];
  is_anomaly: boolean;
  nodes?: ITopoNode[];
  source?: string;
  source_is_anomaly?: boolean;
  source_is_on_alert?: boolean;
  source_name?: string;
  source_type?: string;
  target?: string;
  target_is_anomaly?: boolean;
  target_is_on_alert?: boolean;
  target_name?: string;
  target_type?: string;
}

/** 拓扑图实体数据 */
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

/** 事件详情菜单项 */
export interface IEventTagsItem {
  bk_biz_id: number | string;
  end_time: number; // 故障结束时间/当前时间
  index_info: Record<string, any>;
  interval: number;
  start_time: number; // 当前点击的事件的时间戳
}

/** 指标项 */
export interface IMetricItem {
  display_by_dimensions: boolean; // 是否为多维度指标
  metric_alias: string;
  metric_name: string;
  metric_type: string;
  time_series: Record<string, ITimeSeries>;
}

/** 事件详情数据 */
export interface IncidentDetailData {
  begin_time?: number;
  bk_biz_id: string;
  create_time: number;
  /** 当前快照（结构与故障页 ISnapshot 对齐，避免循环依赖用宽松 Record） */
  current_snapshot?: Record<string, unknown>;
  end_time: number;
  id: string;
  incident_id: string;
  wx_cs_link?: string;
}

/** 事件各数据源分析结果状态 */
export interface IncidentResults {
  [key: string]: any;
  incident_topology: { enabled: boolean; status: string };
}

/** 弹窗位置坐标 */
export interface IPosition {
  left: number;
  top: number;
}

/** 节点排名数据 */
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

/** 时间序列数据 */
export interface ITimeSeries {
  [key: string]: any;
  datapoints: Array<[number, number, number]>; // 指标数据
  unit: string;
}

/** Combo 配置（G6 ModelConfig 扩展） */
export interface ITopoCombo extends ModelConfig {
  [key: string]: any;
  dataType?: string;
  id: number | string;
  label?: string;
}

/** 拓扑完整数据（节点 + 边 + combo） */
export interface ITopoData {
  combos: ITopoCombo[];
  edges: IEdge[];
  nodes: ITopoNode[];
}

/** 拓扑边配置（G6 ModelConfig 扩展） */
export interface ITopoEdge extends ModelConfig {
  aggregated: boolean;
  count: number;
  source: string;
  target: string;
  type: 'dependency' | 'invoke';
}

/** 拓扑图节点数据（G6 ModelConfig 扩展） */
export interface ITopoNode extends ModelConfig {
  aggregated_nodes?: ITopoNode[];
  alert_all_recorved?: boolean;
  alert_ids?: string[];
  anomaly_count?: number;
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
  /** 节点扩展属性（部分场景可缺省） */
  properties?: {
    aggregated_by?: string[];
    entity_category?: string;
    entity_show_type?: string;
  };
}

/** 事件散点图数据 */
export interface MetricEvent {
  event_alias?: string;
  event_level: string;
  event_name: string;
  event_source: string;
  series: EventSeries[];
}

/** 时间轴原始数据帧 */
export interface TopoRawData {
  content: ITopoData[];
  create_time: number;
  fpp_snapshot_id: string;
  incident_id: string;
}

/** 事件分析选中配置项（内部使用） */
interface EventConfigItem {
  is_select_all: boolean;
  list: string[];
}
