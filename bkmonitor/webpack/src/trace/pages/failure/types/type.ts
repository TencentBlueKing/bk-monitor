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

export interface IAlert {
  alert_example: IAlertData;
  alert_ids: string[];
  begin_time: number;
  children: IAlert[];
  count: number;
  end_time: number;
  id: string;
  is_feedback_root: boolean;
  is_root: boolean;
  isDraw: boolean;
  isOpen: boolean;
  isShow: boolean;
  level_name: string;
  name: string;
  related_entities: IAlertData[];
  status: string;
}

export interface IAlertData {
  ack_duration: number;
  ack_operator: string;
  alert_name: string;
  appointee: string[];
  assignee: string[];
  begin_time: number;
  bk_biz_id: number;
  bk_biz_name: string;
  bk_cloud_id: number;
  bk_host_id: number;
  bk_service_instance_id: null;
  bk_topo_node: string[];
  category: string;
  category_display: string;
  converge_id: string;
  create_time: number;
  data_type: string;
  dedupe_keys: string[];
  dedupe_md5: string;
  description: string;
  dimension_message: string;
  dimensions: Array<{ display_key: string; display_value: string; key: string; value: string }>;
  duration: string;
  end_time: number;
  event_id: string;
  first_anomaly_time: number;
  follower: null;
  id: string;
  ip: string;
  ipv6: string;
  is_ack: null;
  is_blocked: boolean;
  is_handled: boolean;
  is_shielded: boolean;
  labels: null;
  latest_time: number;
  metric: string[];
  metric_display: Array<{ id: string; name: string }>;
  plugin_display_name: string;
  plugin_id: string;
  seq_id: number;
  severity: number;
  shield_id: null;
  shield_left_time: string;
  shield_operator: any[];
  stage_display: string;
  status: string;
  strategy_id: number;
  strategy_name: string;
  supervisor: null;
  tags: Array<{ key: string; value: string }>;
  target: string;
  target_key: string;
  target_type: string;
  update_time: number;
  entity: {
    aggregated_entities: any[];
    anomaly_score: number;
    anomaly_type: null;
    bk_biz_id: null;
    dimensions: {
      cluster_id: string;
      namespace: string;
      node_type: string;
      pod_name: string;
    };
    entity_id: string;
    entity_name: string;
    entity_type: string;
    is_anomaly: boolean;
    is_on_alert: boolean;
    is_root: boolean;
    rank: {
      rank_alias: string;
      rank_category: {
        category_alias: string;
        category_id: number;
        category_name: string;
      };
      rank_id: number;
      rank_name: string;
    };
    tags: any;
  };
  extra_info: {
    agg_dimensions: any[];
    cycle_handle_record: {
      [key: string]: {
        execute_times: number;
        is_shielded: boolean;
        last_time: number;
        latest_anomaly_time: number;
      };
    };
    end_description: string;
    is_recovering: boolean;
    matched_rule_info: {
      additional_tags: any[];
      follow_groups: any[];
      group_info: any;
      itsm_actions: any;
      notice_appointees: any[];
      notice_upgrade_user_groups: any[];
      rule_snaps: any;
      severity: number;
    };
    origin_alarm: {
      anomaly: {
        [key: string]: {
          anomaly_id: string;
          anomaly_message: string;
          anomaly_time: string;
        };
      };
      data: {
        access_time: number;
        detect_time: number;
        dimension_fields: string[];
        dimensions: {
          bk_host_id: number;
          bk_target_ip: string;
          bk_topo_node: string[];
          device_name: string;
        };
        record_id: string;
        time: number;
        value: number;
        values: { _result_: number; time: number };
      };
      dimension_translation: {
        [key: string]: {
          display_name: string;
          display_value: string | string[];
          value: number | string | string[];
        };
      };
      strategy_snapshot_key: string;
      trigger: {
        anomaly_ids: string[];
        level: string;
      };
      trigger_time: number;
    };
    recovery_value: number;
    strategy: {
      actions: Array<{
        config: {
          bk_biz_id: string;
          desc: string;
          execute_config: {
            template_detail: {
              authorize: { auth_config: any; auth_type: string };
              body: { content: string; content_type: string; data_type: string; params: any[] };
              failed_retry: { is_enabled: boolean; max_retry_times: number; retry_interval: number; timeout: number };
              headers: any[];
              method: string;
              need_poll: boolean;
              notify_interval: number;
              query_params: any[];
              url: string;
            };
            timeout: number;
          };
          id: number;
          name: string;
          plugin_id: string;
        };
        config_id: number;
        id: number;
        options: {
          converge_config: {
            condition: Array<{ dimension: string; value: string[] }>;
            converge_func: string;
            count: number;
            is_enabled: boolean;
            need_biz_converge: boolean;
            timedelta: number;
          };
          end_time: string;
          start_time: string;
        };
        relate_type: string;
        signal: string[];
        user_groups: number[];
        user_type: string;
      }>;
      app: string;
      bk_biz_id: number;
      create_time: number;
      create_user: string;
      detects: Array<{
        connector: string;
        expression: string;
        id: number;
        level: number;
        recovery_config: {
          check_window: number;
          status_setter: string;
        };
        trigger_config: {
          check_window: number;
          count: number;
          uptime: {
            calendars: any[];
            time_ranges: Array<{ end: string; start: string }>;
          };
        };
      }>;
      edit_allowed: boolean;
      id: number;
      invalid_type: string;
      is_enabled: boolean;
      is_invalid: boolean;
      items: Array<{
        algorithms: Array<{
          config: { ceil: number; floor: number; unit_prefix: string };
          id: number;
          level: number;
          type: string;
        }>;
        expression: string;
        functions: any[];
        id: number;
        metric_type: string;
        name: string;
        no_data_config: {
          agg_dimension: any[];
          continuous: number;
          is_enabled: boolean;
          level: number;
        };
        origin_sql: string;
        query_configs: Array<{
          agg_interval: number;
          alias: string;
          data_source_label: string;
          data_type_label: string;
          functions: any[];
          id: number;
          metric_id: string;
          promql: string;
          target: any[];
        }>;
        query_md5: string;
        target: any[];
        update_time: number;
      }>;
      labels: any[];
      metric_type: string;
      name: string;
      notice: {
        config: {
          interval_notify_mode: string;
          need_poll: boolean;
          notify_interval: number;
          template: Array<{
            message_tmpl: string;
            signal: string;
            title_tmpl: string;
          }>;
        };
        config_id: number;
        id: number;
        options: {
          assign_mode: string[];
          chart_image_enabled: boolean;
          converge_config: {
            condition: Array<{ dimension: string; value: string[] }>;
            converge_func: string;
            count: number;
            is_enabled: boolean;
            need_biz_converge: boolean;
            sub_converge_config: {
              condition: Array<{ dimension: string; value: string[] }>;
              converge_func: string;
              count: number;
              timedelta: number;
            };
            timedelta: number;
          };
          end_time: string;
          exclude_notice_ways: {
            ack: any[];
            closed: any[];
            recovered: any[];
          };
          noise_reduce_config: {
            count: number;
            dimensions: any[];
            is_enabled: boolean;
            timedelta: number;
            unit: string;
          };
          start_time: string;
          upgrade_config: {
            is_enabled: boolean;
            upgrade_interval: number;
            user_groups: any[];
          };
        };
        relate_type: string;
        signal: string[];
        user_groups: number[];
        user_type: string;
      };
      path: string;
      priority: null;
      priority_group_key: string;
      scenario: string;
      source: string;
      type: string;
      update_time: number;
      update_user: string;
      version: string;
    };
  };
}

export interface IAlertObj {
  ids?: string;
  label?: string;
}

export interface IAnomalyAnalysis {
  $index?: number;
  alert_count?: number;
  alerts?: IAlertData[];
  name?: string;
  score?: number;
  dimension_values?: {
    [key: string]: string[];
  };
  strategy_alerts_mapping?: {
    [key: number]: IStrategyMapItem;
  };
}

export interface IContentList {
  anomaly_analysis?: IAnomalyAnalysis[];
  suggestion?: string;
  summary?: string;
}

export type ICurrentISnapshot = ISnapshot;

export interface IDetail {
  dimension?: string;
  severity: number;
  trigger?: string;
  strategy?: {
    id?: number | string;
    name?: string;
  };
}

export interface IEdge {
  edge_type: string;
  source_id: string;
  source_type: string;
  target_id: string;
  target_type: string;
}
export interface IEntityData {
  anomaly_score: number;
  anomaly_type: string;
  entity_id: string;
  entity_name: string;
  entity_type: string;
  is_anomaly: boolean;
  is_root: boolean;
  rank_name: string;
  dimensions: {
    cluster_id: string;
    namespace: string;
    node_type: string;
    pod_name: string;
  };
}

export interface IFilterSearch {
  aggregate_bys: string[];
  bk_biz_id: number;
  bk_biz_ids: number[];
  id: string;
  query_string: string;
  username: string;
}

export interface IIncident {
  alert_count: number;
  assignees: string[];
  begin_time: number;
  bk_biz_id: number;
  bk_biz_name: string;
  create_time: number;
  current_snapshot: ICurrentISnapshot;
  duration: string;
  end_time: null | number;
  handlers: string[];
  id: string;
  incident_id: number;
  incident_name: string;
  incident_reason: string;
  incident_root: IncidentRoot;
  labels: string[];
  level: string;
  level_alias: string;
  snapshot: ISnapshot;
  snapshots: ISnapshot[];
  status: string;
  status_alias: string;
  update_time: number;
}
export interface IListItem {
  icon?: string;
  key?: string;
  message?: string;
  name?: string;
  render?: () => JSX.Element;
}
export interface IncidentNameTemplate {
  affected_types: [[string, string[]]];
  elements: Array<[string, string] | string>;
  template: string;
}

export interface IncidentPropagationGraph {
  edges: IEdge[];
  entities: IEntityData[];
}
export interface ISnapshot {
  alerts: number[];
  bk_biz_id: number[];
  bk_biz_ids?: Array<{ bk_biz_id: number; bk_biz_name: string }>;
  content: ISnapshotContent;
  create_time: number;
  events?: any[];
  extra_info?: any;
  fpp_snapshot_id: string;
  id: string;
  incident_id: number;
  status: string;
  update_time?: any;
}
export interface ISnapshotContent {
  alerts: number;
  anomaly_time: number;
  bk_biz_id: number;
  graph_snapshot_id: string;
  incident_label: string[];
  incident_name: string;
  incident_name_template: IncidentNameTemplate;
  incident_propagation_graph: IncidentPropagationGraph;
  incident_root: [string, string];
  one_hop_neighbors: string[];
  snapshot_id: string;
  timestamp: number;
  incident_alerts: Array<{
    entity_id: string;
    id: string;
    strategy_id: string;
  }>;
  product_hierarchy_category: {
    data_center: {
      category_alias: string;
      category_id: number;
      category_name: string;
    };
    host_platform: {
      category_alias: string;
      category_id: number;
      category_name: string;
    };
    service: {
      category_alias: string;
      category_id: number;
      category_name: string;
    };
  };
  product_hierarchy_rank: {
    idc: {
      rank_alias: string;
      rank_category: string;
      rank_id: number;
      rank_name: string;
    };
    idc_unit: {
      rank_alias: string;
      rank_category: string;
      rank_id: number;
      rank_name: string;
    };
    k8s: {
      rank_alias: string;
      rank_category: string;
      rank_id: number;
      rank_name: string;
    };
    operate_system: {
      rank_alias: string;
      rank_category: string;
      rank_id: number;
      rank_name: string;
    };
    rack: {
      rank_alias: string;
      rank_category: string;
      rank_id: number;
      rank_name: string;
    };
    service_module: {
      rank_alias: string;
      rank_category: string;
      rank_id: number;
      rank_name: string;
    };
  };
}
export interface IStrategyMapItem {
  alerts?: string[];
  strategy_id?: number;
  strategy_name?: string;
}

export interface ITagInfoType {
  bk_biz_id: number;
  bk_biz_name: string;
  isCheck: boolean;
}
export interface IUserName {
  id: string;
  name: string;
}

interface IncidentRoot {
  rca_trace_info: {
    abnormal_traces_query: Record<string, string>;
  };
}
