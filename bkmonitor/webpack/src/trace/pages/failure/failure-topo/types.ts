/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
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
export interface IncidentDetailData {
  bk_biz_id: string;
  create_time: number;
  current_snapshot?: any;
  end_time: number;
  id: string;
  incident_id: string;
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
}

export interface TopoRawData {
  content: ITopoData[];
  create_time: number;
  fpp_snapshot_id: string;
  incident_id: string;
}
