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
  ack_duration: number;
  alert_name: string;
  appointee: string[];
  assignee: string[];
  begin_time: number;
  bk_biz_id: number;
  bk_cloud_id?: number;
  bk_host_id?: number;
  bk_service_instance_id?: number;
  bk_topo_node?: string;
  category: string;
  category_display?: string;
  converge_id: string;
  create_time: number;
  data_type: string;
  dedupe_keys: string[];
  dedupe_md5: string;
  description: string;
  dimension_message: string;
  duration: string;
  end_time: number;
  event_id: string;
  first_anomaly_time: number;
  follower?: string[];
  id: string;
  ip?: string;
  ipv6?: string;
  is_ack: boolean;
  is_blocked: boolean;
  is_handled: boolean;
  is_shielded: boolean;
  labels: string[];
  latest_time: number;
  metric: string[];
  plugin_display_name: string;
  plugin_id: string;
  relation_info: string;
  seq_id: number;
  severity: number;
  shield_id?: string;
  shield_left_time: string;
  stage_display: string;
  status: 'ABNORMAL' | 'CLOSED' | 'RECOVERED'; // 示例状态值
  strategy_id: number;
  strategy_name: string;
  supervisor?: string;
  target?: string;
  target_key: string;
  target_type: string;
  update_time: number;
  dimensions: {
    display_key: string;
    display_value: string;
    key: string;
    value: number | string;
  }[];
  extend_info: {
    data_label: string;
    result_table_id: string;
  };
  extra_info: {
    agg_dimensions: string[];
    cycle_handle_record: Record<
      number,
      {
        execute_times: number;
        is_shielded: boolean;
        last_time: number;
        latest_anomaly_time: number;
      }
    >;
    end_description: string;
    is_recovering: boolean;
    matched_rule_info: Record<string, any>;
    origin_alarm: Record<string, any>;
    recovery_value: number;
    strategy: Record<string, any>;
  };
  graph_panel: {
    id: string;
    subTitle: string;
    targets: Record<string, any>[];
    title: string;
    type: string;
  };
  metric_display: {
    id: string;
    name: string;
  }[];
  tags: {
    key: string;
    value: string;
  }[];
}
