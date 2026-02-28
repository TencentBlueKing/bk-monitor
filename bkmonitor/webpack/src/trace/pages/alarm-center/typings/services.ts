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

import type { ACTION_STORAGE_KEY } from '../services/action-services';
import type { ALERT_STORAGE_KEY } from '../services/alert-services';
import type { INCIDENT_STORAGE_KEY } from '../services/incident-services';
import type { AggFunction, QueryConfig } from 'monitor-pc/pages/query-template/typings';

/**
 * 处理记录 table数据
 */
export type ActionTableItem = {
  action_config: {
    app: string;
    bk_biz_id: number;
    create_time: string;
    create_user: string;
    desc: string;
    execute_config: Record<string, any>;
    hash: string;
    id: number;
    is_builtin: boolean;
    is_deleted: boolean;
    is_enabled: boolean;
    name: string;
    path: string;
    plugin_id: number;
    plugin_name: string;
    plugin_type: string;
    snippet: string;
    update_time: string;
    update_user: string;
  };
  action_config_id: number;
  action_name: string;
  action_plugin: {
    backend_config: Array<{
      function: string;
      name: string;
    }>;
    config_schema: Record<string, any>;
    id: number;
    is_enabled: boolean;
    name: string;
    plugin_key: string;
    plugin_type: string;
    update_time: string;
    update_user: string;
  };
  action_plugin_type: string;
  action_plugin_type_display: string;
  alert_id: string[];
  alert_level: number;
  bk_biz_id: number | string;
  bk_biz_name: string;
  bk_module_ids: null | string[];
  bk_module_names: null | string[];
  bk_set_ids: null | string[];
  bk_set_names: null | string[];
  bk_target_display: string;
  content: {
    [key: string]: any;
    action_plugin_type: string;
    text: string;
    url: string;
  };
  converge_count: number;
  converge_id: number;
  create_time: number;
  dimension_string: string;
  dimensions: Array<{
    display_key: string;
    display_value: string;
    key: string;
    value: string;
  }>;
  duration: string;
  end_time: number;
  ex_data: {
    [key: string]: any;
    message: string;
  };
  execute_times: number;
  failure_type: null | string;
  id: string;
  inputs: {
    [key: string]: any;
    alert_latest_time: number;
    followed: boolean;
    is_alert_shielded: boolean;
    is_unshielded: boolean;
    notice_receiver: string;
    notice_type: string;
    notice_way: string;
    notify_info: Record<string, string[]>;
    shield_detail: string;
    time_range: string;
  };
  is_converge_primary: boolean;
  is_parent_action: boolean;
  operate_target_string: string;
  operator: string[];
  outputs: {
    [key: string]: any;
    message: string;
    title: string;
  };
  parent_action_id: number;
  raw_id: number;
  related_action_ids: null | number[];
  signal: string;
  signal_display: string;
  status: string;
  status_tips: string;
  strategy_id: number;
  strategy_name: string;
  update_time: number;
};
export type AlarmStorageKey = typeof ACTION_STORAGE_KEY | typeof ALERT_STORAGE_KEY | typeof INCIDENT_STORAGE_KEY;

export type AlertActionOverview = {
  children: { count: number; id: 'failure' | 'success'; name: string }[];
  count: number;
  id: string;
  name: string;
};

/** 告警 -- 告警内容详情 */
export interface AlertContentItem {
  expression: string;
  function: AggFunction[];
  id: number;
  name: string;
  origin_sql: string;
  query_configs: QueryConfig[];
}
/** 告警 -- 告警内容详情 -- 数据含义修改事件对象 */
export type AlertContentNameEditInfo = {
  alert_id: AlertTableItem['id'];
  bk_biz_id?: number;
  data_meaning: AlertContentItem['name'];
};

/** 告警 -- 关联事件数接口返回数据类型 */
export type AlertEventCountResult = Record<string, number>;

export interface AlertExtendInfoItem {
  data_label: string;
  hostname?: string;
  result_table_id: string;
  topo_info?: string;
  type?: string;
}
/** 告警 -- 关联告警信息接口返回数据类型 */
export type AlertExtendInfoResult = Record<string, AlertExtendInfoItem>;

/**
 * 告警 table 数据
 */
export type AlertTableItem = {
  ack_duration: null | string;
  ack_operator: string;
  alert_name: string;
  appointee: string[];
  assignee: string[];
  begin_time: number;
  bk_biz_id: number;
  bk_biz_name: string;
  bk_cloud_id: null | string;
  bk_host_id: null | string;
  bk_service_instance_id: null | string;
  bk_topo_node: null | string;
  category: string;
  category_display: string;
  converge_id: string;
  create_time: number;
  data_type: string;
  dedupe_keys: string[];
  dedupe_md5: string;
  description: string;
  dimension_message: string;
  dimensions: Array<{
    display_key: string;
    display_value: string;
    key: string;
    value: string;
  }>;
  duration: string;
  end_time: null | number;
  event_count?: number;
  event_id: string;
  extend_info?: AlertExtendInfoItem;
  first_anomaly_time: number;
  follower: null | string[];
  followerDisabled?: boolean;
  id: string;
  ip: null | string;
  ipv6: null | string;
  is_ack: boolean | null;
  is_blocked: boolean;
  is_handled: boolean;
  is_shielded: boolean;
  items: AlertContentItem[];
  labels: string[];
  latest_time: number;
  metric: string[];
  metric_display: Array<{
    id: string;
    name: string;
  }>;
  plugin_display_name: string;
  plugin_id: string;
  seq_id: number;
  severity: number;
  shield_id: null | string;
  shield_left_time: string;
  shield_operator: string[];
  stage_display: string;
  status: string;
  strategy_id: number;
  strategy_name: string;
  supervisor: null | string;
  tags: Array<{
    key: string;
    value: string;
  }>;
  target: null | string;
  target_key: string;
  target_type: string;
  update_time: number;
};

// 单个分桶
export type AnalysisBucket = {
  count: number;
  id: string;
  name: string;
};

// 某个分析字段的聚合结果
export type AnalysisFieldAggItem = {
  bucket_count: number; // 分桶总数
  buckets: AnalysisBucket[]; // 分桶明细
  field: string; // 字段名，如 bk_biz_id
  is_char: boolean; // 是否为字符型
};
export interface AnalysisListItem extends AnalysisFieldAggItem {
  buckets: AnalysisListItemBucket[];
  name: string;
}

export type AnalysisListItemBucket = AnalysisBucket & { percent: number };

export type AnalysisTopNDataResponse<T> = {
  doc_count: number;
  fields: T[];
};

export type CommonCondition = {
  condition?: string;
  key: string;
  method?: string;
  value: number[] | string[];
};

export type CommonFilterParams = {
  bk_biz_id: number;
  bk_biz_ids: number[];
  conditions: CommonCondition[];
  end_time: number;
  ordering: string[];
  page: number;
  page_size: number;
  query_string: string;
  record_history: boolean;
  start_time: number;
  status: string[];
};

export type FilterTableResponse<T> = {
  data: T[];
  total: number;
};

/**
 * 故障处理 table 数据
 */
export type IncidentTableItem = {
  alert_count: number;
  assignees: string[];
  begin_time: number;
  bk_biz_id: string;
  bk_biz_name: string;
  create_time: number;
  duration: string;
  end_time: number;
  handlers: string[];
  id: string;
  incident_id: number;
  incident_name: string;
  incident_reason: null | string;
  labels: string[];
  level: string;
  level_alias: string;
  snapshot: {
    alerts: string[];
    bk_biz_ids: number[];
    content: {
      anomaly_time: number;
      bk_biz_id: string;
      incident_alert_ids: {
        all: string[];
        related: string[];
        unrelated: string[];
      };
      incident_alerts: Array<{
        alert_status: string;
        alert_time: number;
        entity_id: string;
        id: string;
        strategy_id: string;
      }>;
      incident_name: string;
      incident_name_template: {
        affected_types: any[];
        elements: any[];
        template: string;
      };
      incident_propagation_graph: {
        edges: Array<{
          anomaly_score: number;
          component_type: string;
          edge_cluster_id?: null | string;
          edge_type: string;
          events: Array<{
            direction: string;
            event_name: string;
            event_time: number;
            event_type: string;
            metric_name: string;
            time_series: number[][];
          }>;
          is_anomaly: boolean;
          source_id: string;
          source_type: string;
          target_id: string;
          target_type: string;
        }>;
        entities: Array<{
          bk_biz_id: null | string;
          component_type: string;
          dimensions: Record<string, any>;
          entity_id: string;
          entity_name: string;
          entity_type: string;
          is_anomaly: boolean;
          is_on_alert: boolean;
          is_root: boolean;
          observe_time_rage: {
            end_at: number;
            start_at: number;
          };
          properties: Record<string, any>;
          rank_name: string;
          tags: Record<string, any>;
        }>;
      };
      incident_root: string[];
      product_hierarchy_category: Record<
        string,
        {
          category_alias: string;
          category_id: number;
          category_name: string;
          layer_alias: string;
          layer_name: string;
        }
      >;
      product_hierarchy_rank: Record<
        string,
        {
          rank_alias: string;
          rank_category: string;
          rank_id: number;
          rank_name: string;
        }
      >;
      rca_summary: {
        action: string;
        bk_biz_ids: string[];
        graph_latest_time: number;
        graph_snapshot_info: Record<string, any>;
        incident_alert_ids: {
          all: string[];
          related: string[];
          unrelated: string[];
        };
        incident_bk_biz_id: string;
        incident_handling_suggestions: string;
        incident_label: string;
        incident_name: string;
        incident_summary: string;
        k8s_events_summary: string;
        k8s_warning_events: any[];
        properties: Array<{
          tags: Record<string, any>;
          target_id: null | string;
          target_type: string;
        }>;
        rca_graph_version: {
          end_time_ms: number;
          periods_set: number[][];
          start_time_ms: number;
        };
        rca_mode: string;
        rca_snapshot_info: {
          snapshot_id: string;
        };
        root_cause: string;
        status: number;
        timestamp: number;
      };
      snapshot_id: string;
      timestamp: number;
    };
    create_time: number;
    events: any[];
    extra_info: Record<string, any>;
    fpp_snapshot_id: string;
    id: string;
    incident_id: number;
    status: string;
    update_time: null | number;
  };
  status: string;
  status_alias: string;
  status_order: number;
  update_time: number;
};

export type QuickFilterItem = {
  children?: QuickFilterItem[];
  count?: number;
  icon?: string;
  iconColor?: string;
  id: string;
  name: string;
  textColor?: string;
};
