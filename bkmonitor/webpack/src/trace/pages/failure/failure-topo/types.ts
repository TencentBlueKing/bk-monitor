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

export interface IEntityTag {
  cluster_id: string;
  name: string;
  namespace: string;
}

export interface IEntity {
  aggregated_entites: IEntity[];
  anomaly_score: number;
  anomaly_type: string;
  alert_all_recorved: boolean;
  entity_id: string;
  entity_name: string;
  entity_type: string;
  is_anomaly: boolean;
  is_feedback_root: boolean;
  is_root: boolean;
  is_on_alert: boolean;
  rank: IRank;
  dimensions: Record<string, any>;
  tags?: {
    BcsService?: IEntityTag;
    BcsWorkload?: IEntityTag;
  };
  observe_time_rage?: {
    start_at: number | string;
    end_at: number | string;
  };
  rca_trace_info?: {
    abnormal_message: string;
    abnormal_traces: Record<string, any>[];
    abnormal_traces_query: Record<string, any>;
  };
}

export interface IEdge {
  [key: string]: any;
  is_anomaly: boolean;
  edge_type: string;
  events: Record<string, any>[];
}
export interface IncidentDetailData {
  id: string;
  incident_id: string;
  bk_biz_id: string;
  end_time: number;
  create_time: number;
  current_snapshot?: any;
}

export interface IRank {
  rank_id: number;
  rank_name: string;
  rank_alias: string;
  nodes: ITopoNode[];
  anomaly_count: number;
  total: number;
  is_sub_rank: boolean;
  rank_category: {
    category_alias: string;
    category_id: number;
    category_name: string;
  };
}

export interface ITopoNode extends ModelConfig {
  node?: any;
  aggregated_nodes?: ITopoNode[];
  comboId?: string;
  entity?: IEntity;
  originComboId?: string;
  is_feedback_root?: boolean;
  id?: string;
  is_deleted?: boolean;
  subComboId?: string;
  bk_biz_id?: string;
  bk_biz_name?: string;
  alert_display?: {
    alert_id: string;
    alert_name: string;
  };
  alert_ids?: string[];
}

export interface ITopoEdge extends ModelConfig {
  count: number;
  source: string;
  target: string;
  type: 'dependency' | 'invoke';
  aggregated: boolean;
}

export interface ITopoCombo extends ModelConfig {
  dataType?: string;
  id: number | string;
  label?: string;
  [key: string]: any;
}

export interface ITopoData {
  combos: ITopoCombo[];
  edges: IEdge[];
  nodes: ITopoNode[];
}

export interface TopoRawData {
  create_time: number;
  fpp_snapshot_id: string;
  incident_id: string;
  content: ITopoData[];
}
