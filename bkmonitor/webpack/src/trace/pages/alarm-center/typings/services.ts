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
export type CommonCondition = {
  key: string;
  value: string[];
  condition?: string;
  method: string;
};
export type CommonFilterParams = {
  bk_biz_ids: number[];
  status: string[];
  conditions: CommonCondition[];
  query_string: string;
  start_time: number;
  end_time: number;
  page: number;
  page_size: number;
  record_history: boolean;
  bk_biz_id: number;
  ordering: string[];
};

export type QuickFilterItem = {
  id: string;
  name: string;
  count?: number;
  children?: QuickFilterItem[];
};

/**
 * 告警 table 数据
 */
export type AlertTableItem = {
  id: string;
  alert_name: string;
  status: string;
  description: string;
  severity: number;
  metric: string[];
  labels: string[];
  bk_biz_id: number;
  ip: null | string;
  ipv6: null | string;
  bk_host_id: null | string;
  bk_cloud_id: null | string;
  bk_service_instance_id: null | string;
  bk_topo_node: null | string;
  assignee: string[];
  appointee: string[];
  supervisor: null | string;
  follower: null | string;
  is_ack: boolean | null;
  is_shielded: boolean;
  shield_left_time: string;
  shield_id: null | string;
  is_handled: boolean;
  is_blocked: boolean;
  strategy_id: number;
  create_time: number;
  update_time: number;
  begin_time: number;
  end_time: null | number;
  latest_time: number;
  first_anomaly_time: number;
  target_type: string;
  target: null | string;
  category: string;
  tags: Array<{
    value: string;
    key: string;
  }>;
  category_display: string;
  duration: string;
  ack_duration: null | string;
  data_type: string;
  converge_id: string;
  event_id: string;
  plugin_id: string;
  plugin_display_name: string;
  strategy_name: string;
  stage_display: string;
  dimensions: Array<{
    display_value: string;
    display_key: string;
    value: string;
    key: string;
  }>;
  seq_id: number;
  dedupe_md5: string;
  dedupe_keys: string[];
  dimension_message: string;
  metric_display: Array<{
    id: string;
    name: string;
  }>;
  target_key: string;
  ack_operator: string;
  shield_operator: string[];
  bk_biz_name: string;
};

/**
 * 处理记录 table数据
 */
export type ActionTableItem = {
  id: number | string;
  converge_id: number;
  is_converge_primary: boolean;
  status: string;
  failure_type: null | string;
  ex_data: {
    message: string;
    [key: string]: any;
  };
  strategy_id: number;
  strategy_name: string;
  signal: string;
  alert_id: string[];
  alert_level: number;
  operator: string[];
  inputs: {
    notice_way: string;
    notice_receiver: string;
    followed: boolean;
    alert_latest_time: number;
    is_alert_shielded: boolean;
    shield_detail: string;
    is_unshielded: boolean;
    notice_type: string;
    time_range: string;
    notify_info: Record<string, string[]>;
    [key: string]: any;
  };
  outputs: {
    title: string;
    message: string;
    [key: string]: any;
  };
  execute_times: number;
  action_plugin_type: string;
  action_plugin: {
    id: number;
    name: string;
    plugin_type: string;
    plugin_key: string;
    update_user: string;
    update_time: string;
    is_enabled: boolean;
    config_schema: Record<string, any>;
    backend_config: Array<{
      function: string;
      name: string;
    }>;
  };
  action_name: string;
  action_config: {
    id: number;
    plugin_id: number;
    desc: string;
    execute_config: Record<string, any>;
    name: string;
    bk_biz_id: number;
    is_enabled: boolean;
    is_deleted: boolean;
    create_user: string;
    create_time: string;
    update_user: string;
    update_time: string;
    is_builtin: boolean;
    app: string;
    path: string;
    hash: string;
    snippet: string;
    plugin_name: string;
    plugin_type: string;
  };
  action_config_id: number;
  is_parent_action: boolean;
  related_action_ids: null | number[];
  parent_action_id: number;
  create_time: number;
  update_time: number;
  end_time: number;
  bk_target_display: string;
  bk_biz_id: number | string;
  bk_biz_name: string;
  bk_set_ids: null | string[];
  bk_set_names: null | string[];
  bk_module_ids: null | string[];
  bk_module_names: null | string[];
  raw_id: number;
  duration: string;
  operate_target_string: string;
  content: {
    text: string;
    action_plugin_type: string;
    url: string;
    [key: string]: any;
  };
  dimensions: Array<{
    key: string;
    value: string;
    display_key: string;
    display_value: string;
  }>;
  dimension_string: string;
  status_tips: string;
  converge_count: number;
  action_plugin_type_display: string;
  signal_display: string;
};

/**
 * 故障处理 table 数据
 */
export type IncidentTableItem = {
  id: string;
  incident_id: number;
  incident_name: string;
  incident_reason: null | string;
  bk_biz_id: string;
  status: string;
  status_order: number;
  level: string;
  assignees: string[];
  handlers: string[];
  labels: string[];
  create_time: number;
  update_time: number;
  begin_time: number;
  end_time: number;
  snapshot: {
    id: string;
    incident_id: number;
    bk_biz_ids: number[];
    status: string;
    alerts: string[];
    create_time: number;
    content: {
      timestamp: number;
      anomaly_time: number;
      incident_name: string;
      incident_alerts: Array<{
        alert_status: string;
        alert_time: number;
        strategy_id: string;
        id: string;
        entity_id: string;
      }>;
      incident_root: string[];
      incident_name_template: {
        template: string;
        elements: any[];
        affected_types: any[];
      };
      rca_summary: {
        graph_snapshot_info: Record<string, any>;
        properties: Array<{
          target_type: string;
          target_id: null | string;
          tags: Record<string, any>;
        }>;
        k8s_events_summary: string;
        k8s_warning_events: any[];
        incident_summary: string;
        incident_handling_suggestions: string;
        bk_biz_ids: string[];
        incident_bk_biz_id: string;
        root_cause: string;
        rca_mode: string;
        rca_graph_version: {
          start_time_ms: number;
          end_time_ms: number;
          periods_set: number[][];
        };
        incident_alert_ids: {
          related: string[];
          unrelated: string[];
          all: string[];
        };
        status: number;
        graph_latest_time: number;
        incident_name: string;
        incident_label: string;
        timestamp: number;
        rca_snapshot_info: {
          snapshot_id: string;
        };
        action: string;
      };
      incident_alert_ids: {
        related: string[];
        unrelated: string[];
        all: string[];
      };
      product_hierarchy_category: Record<
        string,
        {
          category_id: number;
          category_name: string;
          category_alias: string;
          layer_name: string;
          layer_alias: string;
        }
      >;
      product_hierarchy_rank: Record<
        string,
        {
          rank_id: number;
          rank_name: string;
          rank_alias: string;
          rank_category: string;
        }
      >;
      incident_propagation_graph: {
        entities: Array<{
          is_anomaly: boolean;
          rank_name: string;
          entity_name: string;
          bk_biz_id: null | string;
          observe_time_rage: {
            end_at: number;
            start_at: number;
          };
          entity_id: string;
          is_root: boolean;
          tags: Record<string, any>;
          component_type: string;
          entity_type: string;
          is_on_alert: boolean;
          properties: Record<string, any>;
          dimensions: Record<string, any>;
        }>;
        edges: Array<{
          edge_cluster_id?: null | string;
          anomaly_score: number;
          component_type: string;
          is_anomaly: boolean;
          target_type: string;
          source_type: string;
          target_id: string;
          source_id: string;
          edge_type: string;
          events: Array<{
            event_type: string;
            metric_name: string;
            time_series: number[][];
            event_name: string;
            event_time: number;
            direction: string;
          }>;
        }>;
      };
      bk_biz_id: string;
      snapshot_id: string;
    };
    fpp_snapshot_id: string;
    events: any[];
    update_time: null | number;
    extra_info: Record<string, any>;
  };
  alert_count: number;
  status_alias: string;
  level_alias: string;
  duration: string;
  bk_biz_name: string;
};
export type FilterTableResponse<T> = {
  total: number;
  data: T[];
};

export type AnalysisTopNDataResponse<T> = {
  doc_count: number;
  fields: T[];
};

// 单个分桶
export type AnalysisBucket = {
  id: string;
  name: string;
  count: number;
};

// 某个分析字段的聚合结果
export type AnalysisFieldAggItem = {
  field: string; // 字段名，如 bk_biz_id
  is_char: boolean; // 是否为字符型
  bucket_count: number; // 分桶总数
  buckets: AnalysisBucket[]; // 分桶明细
};
