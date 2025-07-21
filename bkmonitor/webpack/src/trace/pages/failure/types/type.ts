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

export interface IncidentNameTemplate {
  template: string;
  elements: Array<[string, string] | string>;
  affected_types: [[string, string[]]];
}

export interface IEntityData {
  entity_id: string;
  entity_name: string;
  entity_type: string;
  is_anomaly: boolean;
  anomaly_score: number;
  anomaly_type: string;
  is_root: boolean;
  rank_name: string;
  dimensions: {
    node_type: string;
    cluster_id: string;
    namespace: string;
    pod_name: string;
  };
}

export interface IEdge {
  source_type: string;
  target_type: string;
  source_id: string;
  target_id: string;
  edge_type: string;
}

export interface IncidentPropagationGraph {
  entities: IEntityData[];
  edges: IEdge[];
}

export interface ISnapshotContent {
  snapshot_id: string;
  timestamp: number;
  alerts: number;
  bk_biz_id: number;
  incident_alerts: Array<{
    id: string;
    strategy_id: string;
    entity_id: string;
  }>;
  incident_name: string;
  incident_name_template: IncidentNameTemplate;
  incident_root: [string, string];
  incident_label: string[];
  product_hierarchy_category: {
    service: {
      category_id: number;
      category_name: string;
      category_alias: string;
    };
    host_platform: {
      category_id: number;
      category_name: string;
      category_alias: string;
    };
    data_center: {
      category_id: number;
      category_name: string;
      category_alias: string;
    };
  };
  product_hierarchy_rank: {
    service_module: {
      rank_id: number;
      rank_name: string;
      rank_alias: string;
      rank_category: string;
    };
    k8s: {
      rank_id: number;
      rank_name: string;
      rank_alias: string;
      rank_category: string;
    };
    operate_system: {
      rank_id: number;
      rank_name: string;
      rank_alias: string;
      rank_category: string;
    };
    rack: {
      rank_id: number;
      rank_name: string;
      rank_alias: string;
      rank_category: string;
    };
    idc_unit: {
      rank_id: number;
      rank_name: string;
      rank_alias: string;
      rank_category: string;
    };
    idc: {
      rank_id: number;
      rank_name: string;
      rank_alias: string;
      rank_category: string;
    };
  };
  incident_propagation_graph: IncidentPropagationGraph;
  one_hop_neighbors: string[];
  anomaly_time: number;
  graph_snapshot_id: string;
}

export interface ISnapshot {
  incident_id: number;
  bk_biz_id: number[];
  status: string;
  alerts: number[];
  create_time: number;
  content: ISnapshotContent;
  fpp_snapshot_id: string;
  id: string;
  bk_biz_ids?: Array<{ bk_biz_id: number; bk_biz_name: string }>;
  events?: any[];
  update_time?: any;
  extra_info?: any;
}

export type ICurrentISnapshot = ISnapshot;

interface IncidentRoot {
  rca_trace_info: {
    abnormal_traces_query: Record<string, string>;
  };
}
export interface IIncident {
  id: string;
  incident_id: number;
  incident_name: string;
  incident_reason: string;
  bk_biz_id: number;
  status: string;
  level: string;
  assignees: string[];
  handlers: string[];
  labels: string[];
  create_time: number;
  update_time: number;
  begin_time: number;
  end_time: null | number;
  snapshot: ISnapshot;
  status_alias: string;
  level_alias: string;
  alert_count: number;
  duration: string;
  snapshots: ISnapshot[];
  incident_root: IncidentRoot;
  bk_biz_name: string;
  current_snapshot: ICurrentISnapshot;
}

export interface IAlertData {
  id: string;
  alert_name: string;
  status: string;
  description: string;
  severity: number;
  metric: string[];
  labels: null;
  bk_biz_id: number;
  ip: string;
  ipv6: string;
  bk_host_id: number;
  bk_cloud_id: number;
  bk_service_instance_id: null;
  bk_topo_node: string[];
  assignee: string[];
  appointee: string[];
  supervisor: null;
  follower: null;
  is_ack: null;
  is_shielded: boolean;
  shield_left_time: string;
  shield_id: null;
  is_handled: boolean;
  is_blocked: boolean;
  strategy_id: number;
  create_time: number;
  update_time: number;
  begin_time: number;
  end_time: number;
  latest_time: number;
  first_anomaly_time: number;
  target_type: string;
  target: string;
  category: string;
  tags: Array<{ key: string; value: string }>;
  category_display: string;
  duration: string;
  ack_duration: number;
  data_type: string;
  converge_id: string;
  event_id: string;
  plugin_id: string;
  plugin_display_name: string;
  strategy_name: string;
  stage_display: string;
  dimensions: Array<{ key: string; value: string; display_key: string; display_value: string }>;
  seq_id: number;
  dedupe_md5: string;
  dedupe_keys: string[];
  extra_info: {
    origin_alarm: {
      trigger_time: number;
      data: {
        time: number;
        value: number;
        values: { _result_: number; time: number };
        dimensions: {
          bk_target_ip: string;
          device_name: string;
          bk_topo_node: string[];
          bk_host_id: number;
        };
        record_id: string;
        dimension_fields: string[];
        access_time: number;
        detect_time: number;
      };
      trigger: {
        level: string;
        anomaly_ids: string[];
      };
      anomaly: {
        [key: string]: {
          anomaly_message: string;
          anomaly_id: string;
          anomaly_time: string;
        };
      };
      dimension_translation: {
        [key: string]: {
          value: number | string | string[];
          display_name: string;
          display_value: string | string[];
        };
      };
      strategy_snapshot_key: string;
    };
    strategy: {
      id: number;
      version: string;
      bk_biz_id: number;
      name: string;
      source: string;
      scenario: string;
      type: string;
      items: Array<{
        algorithms: Array<{
          level: number;
          id: number;
          type: string;
          config: { ceil: number; floor: number; unit_prefix: string };
        }>;
        update_time: number;
        expression: string;
        origin_sql: string;
        functions: any[];
        query_configs: Array<{
          metric_id: string;
          promql: string;
          data_type_label: string;
          functions: any[];
          agg_interval: number;
          alias: string;
          id: number;
          data_source_label: string;
          target: any[];
        }>;
        query_md5: string;
        name: string;
        metric_type: string;
        id: number;
        no_data_config: {
          is_enabled: boolean;
          level: number;
          continuous: number;
          agg_dimension: any[];
        };
        target: any[];
      }>;
      detects: Array<{
        expression: string;
        trigger_config: {
          check_window: number;
          count: number;
          uptime: {
            calendars: any[];
            time_ranges: Array<{ start: string; end: string }>;
          };
        };
        connector: string;
        level: number;
        id: number;
        recovery_config: {
          check_window: number;
          status_setter: string;
        };
      }>;
      actions: Array<{
        user_type: string;
        config_id: number;
        options: {
          start_time: string;
          converge_config: {
            is_enabled: boolean;
            condition: Array<{ value: string[]; dimension: string }>;
            timedelta: number;
            count: number;
            need_biz_converge: boolean;
            converge_func: string;
          };
          end_time: string;
        };
        id: number;
        signal: string[];
        config: {
          execute_config: {
            template_detail: {
              failed_retry: { is_enabled: boolean; retry_interval: number; max_retry_times: number; timeout: number };
              headers: any[];
              notify_interval: number;
              method: string;
              query_params: any[];
              body: { content_type: string; data_type: string; params: any[]; content: string };
              authorize: { auth_type: string; auth_config: any };
              url: string;
              need_poll: boolean;
            };
            timeout: number;
          };
          plugin_id: string;
          bk_biz_id: string;
          name: string;
          id: number;
          desc: string;
        };
        user_groups: number[];
        relate_type: string;
      }>;
      notice: {
        id: number;
        config_id: number;
        user_groups: number[];
        user_type: string;
        signal: string[];
        options: {
          end_time: string;
          start_time: string;
          assign_mode: string[];
          upgrade_config: {
            is_enabled: boolean;
            user_groups: any[];
            upgrade_interval: number;
          };
          converge_config: {
            count: number;
            condition: Array<{ dimension: string; value: string[] }>;
            timedelta: number;
            is_enabled: boolean;
            converge_func: string;
            need_biz_converge: boolean;
            sub_converge_config: {
              timedelta: number;
              count: number;
              condition: Array<{ dimension: string; value: string[] }>;
              converge_func: string;
            };
          };
          chart_image_enabled: boolean;
          exclude_notice_ways: {
            ack: any[];
            closed: any[];
            recovered: any[];
          };
          noise_reduce_config: {
            unit: string;
            count: number;
            timedelta: number;
            dimensions: any[];
            is_enabled: boolean;
          };
        };
        relate_type: string;
        config: {
          need_poll: boolean;
          notify_interval: number;
          interval_notify_mode: string;
          template: Array<{
            title_tmpl: string;
            message_tmpl: string;
            signal: string;
          }>;
        };
      };
      is_enabled: boolean;
      is_invalid: boolean;
      invalid_type: string;
      update_time: number;
      update_user: string;
      create_time: number;
      create_user: string;
      labels: any[];
      app: string;
      path: string;
      priority: null;
      priority_group_key: string;
      edit_allowed: boolean;
      metric_type: string;
    };
    agg_dimensions: any[];
    matched_rule_info: {
      notice_upgrade_user_groups: any[];
      follow_groups: any[];
      notice_appointees: any[];
      itsm_actions: any;
      severity: number;
      additional_tags: any[];
      rule_snaps: any;
      group_info: any;
    };
    cycle_handle_record: {
      [key: string]: {
        execute_times: number;
        is_shielded: boolean;
        last_time: number;
        latest_anomaly_time: number;
      };
    };
    is_recovering: boolean;
    end_description: string;
    recovery_value: number;
  };
  dimension_message: string;
  metric_display: Array<{ id: string; name: string }>;
  target_key: string;
  ack_operator: string;
  shield_operator: any[];
  bk_biz_name: string;
  entity: {
    entity_id: string;
    entity_name: string;
    entity_type: string;
    is_anomaly: boolean;
    is_root: boolean;
    rank: {
      rank_id: number;
      rank_name: string;
      rank_alias: string;
      rank_category: {
        category_id: number;
        category_name: string;
        category_alias: string;
      };
    };
    dimensions: {
      node_type: string;
      cluster_id: string;
      namespace: string;
      pod_name: string;
    };
    anomaly_score: number;
    anomaly_type: null;
    is_on_alert: boolean;
    bk_biz_id: null;
    tags: any;
    aggregated_entities: any[];
  };
}

export interface IAlert {
  id: string;
  name: string;
  level_name: string;
  count: number;
  related_entities: IAlertData[];
  children: IAlert[];
  alert_ids: string[];
  is_root: boolean;
  is_feedback_root: boolean;
  begin_time: number;
  end_time: number;
  status: string;
  alert_example: IAlertData;
  isOpen: boolean;
  isShow: boolean;
  isDraw: boolean;
}
export interface IFilterSearch {
  id: string;
  aggregate_bys: string[];
  bk_biz_ids: number[];
  query_string: string;
  username: string;
  bk_biz_id: number;
}
export interface IUserName {
  id: string;
  name: string;
}

export interface ITagInfoType {
  bk_biz_id: number;
  bk_biz_name: string;
  isCheck: boolean;
}
export interface IDetail {
  severity: number;
  dimension?: string;
  trigger?: string;
  strategy?: {
    name?: string;
    id?: number | string;
  };
}
export interface IAlertObj {
  ids?: string;
  label?: string;
}
export interface IStrategyMapItem {
  strategy_id?: number;
  strategy_name?: string;
  alerts?: string[];
}

export interface IAnomalyAnalysis {
  name?: string;
  $index?: number;
  score?: number;
  alert_count?: number;
  dimension_values?: {
    [key: string]: string[];
  };
  alerts?: IAlertData[];
  strategy_alerts_mapping?: {
    [key: number]: IStrategyMapItem;
  };
}
export interface IContentList {
  suggestion?: string;
  anomaly_analysis?: IAnomalyAnalysis[];
  summary?: string;
}

export interface IListItem {
  name?: string;
  key?: string;
  icon?: string;
  message?: string;
  render?: () => JSX.Element;
}
