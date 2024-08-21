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

export interface Alert {
  id: string;
  name: string;
  level_name: string;
  count: number;
  related_entities: string[];
  children: Alert[];
  alert_ids: string[];
  is_root: boolean;
  is_feedback_root: boolean;
  begin_time: null | number;
  end_time: null | number;
  status: null | string;
  alert_example: IAlertExample | null;
}

export interface IAlertExample {
  id: string;
  alert_name: string;
  status: string;
  description: string;
  severity: number;
  metric: string[];
  labels: any | null;
  bk_biz_id: number;
  ip: string;
  ipv6: string;
  bk_host_id: number;
  bk_cloud_id: number;
  bk_service_instance_id: any | null;
  bk_topo_node: string[];
  assignee: string[];
  appointee: string[];
  supervisor: any | null;
  follower: any | null;
  is_ack: any | null;
  is_shielded: boolean;
  shield_left_time: string;
  shield_id: any | null;
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
  tags: ITag[];
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
  dimensions: IDimension[];
  seq_id: number;
  dedupe_md5: string;
  dedupe_keys: string[];
  extra_info: IExtraInfo;
}

export interface ITag {
  value: string;
  key: string;
}

export interface IDimension {
  display_value: string;
  display_key: string;
  value: number | string;
  key: string;
}

export interface IExtraInfo {
  origin_alarm: OriginAlarm;
  strategy: IStrategy;
}

export interface OriginAlarm {
  trigger_time: number;
  data: AlarmData;
  trigger: IAlarmTrigger;
  anomaly: Record<string, IAnomaly>;
  dimension_translation: IDimensionTranslation;
  strategy_snapshot_key: string;
}

export interface AlarmData {
  time: number;
  value: number;
  values: Record<string, number>;
  dimensions: Record<string, any>;
  record_id: string;
  dimension_fields: string[];
  access_time: number;
  detect_time: number;
}

export interface IAlarmTrigger {
  level: string;
  anomaly_ids: string[];
}

export interface IAnomaly {
  anomaly_message: string;
  anomaly_id: string;
  anomaly_time: string;
}

export interface IDimensionTranslation {
  bk_target_ip: ITranslationValue;
  device_name: ITranslationValue;
  bk_topo_node: ITranslationValue<ITranslationNode[]>;
  bk_host_id: ITranslationValue;
}

export interface ITranslationValue<T = string> {
  value: T;
  display_name: string;
  display_value: T;
}

export interface ITranslationNode {
  bk_obj_name: string;
  bk_inst_name: string;
}

export interface IStrategy {
  id: number;
  version: string;
  bk_biz_id: number;
  name: string;
  source: string;
  scenario: string;
  type: string;
  items: IStrategyItem[];
  detects: IDetect[];
  actions: IAction[];
  notice: INotice;
  is_enabled: boolean;
  is_invalid: boolean;
  invalid_type: string;
  update_time: number;
  update_user: string;
  create_time: number;
  create_user: string;
  labels: string[];
  app: string;
  path: string;
  priority: null | number;
  priority_group_key: string;
  edit_allowed: boolean;
  metric_type: string;
}

export interface IStrategyItem {
  algorithms: IAlgorithm[];
  update_time: number;
  expression: string;
  origin_sql: string;
  functions: any[];
  query_configs: IQueryConfig[];
  query_md5: string;
  name: string;
  metric_type: string;
  id: number;
  no_data_config: INoDataConfig;
  target: any[];
}

export interface IAlgorithm {
  level: number;
  id: number;
  type: string;
  config: any;
  unit_prefix: string;
}

export interface IQueryConfig {
  metric_id: string;
  data_type_label: string;
  functions: any[];
  result_table_id: string;
  agg_interval: number;
  metric_field: string;
  agg_condition: any[];
  unit: string;
  agg_method: string;
  agg_dimension: string[];
  alias: string;
  id: number;
  data_source_label: string;
}

export interface INoDataConfig {
  is_enabled: boolean;
  level: number;
  continuous: number;
  agg_dimension: string[];
}

export interface IDetect {
  expression: string;
  trigger_config: ITriggerConfig;
  connector: string;
  level: number;
  id: number;
  recovery_config: IRecoveryConfig;
}

export interface ITriggerConfig {
  check_window: number;
  count: number;
  uptime: IUptime;
}

export interface IUptime {
  calendars: any[];
  time_ranges: ITimeRange[];
}

export interface ITimeRange {
  start: string;
  end: string;
}

export interface IRecoveryConfig {
  check_window: number;
  status_setter: string;
}

export interface IAction {
  user_type: string;
  config_id: number;
  options: IActionOptions;
  id: number;
  signal: string[];
  config: IActionConfig;
  user_groups: number[];
  relate_type: string;
}

export interface IActionOptions {
  start_time: string;
  converge_config: IConvergeConfig;
  end_time: string;
}

export interface IConvergeConfig {
  is_enabled: boolean;
  condition: ICondition[];
  timedelta: number;
  count: number;
  need_biz_converge: boolean;
  converge_func: string;
  sub_converge_config?: ISubIConvergeConfig;
}

export interface ICondition {
  value: string[];
  dimension: string;
}

export interface ISubIConvergeConfig {
  timedelta: number;
  count: number;
  condition: ICondition[];
  converge_func: string;
}

export interface IActionConfig {
  execute_config: IExecuteConfig;
  plugin_id: string;
  bk_biz_id: string;
  name: string;
  id: number;
  desc: string;
}

export interface IExecuteConfig {
  template_detail: ITemplateDetail;
  timeout: number;
}

export interface ITemplateDetail {
  failed_retry: IFailedRetry;
  headers: any[];
  notify_interval: number;
  method: string;
  query_params: any[];
  body: IRequestBody;
  authorize: IAuthorize;
  url: string;
  need_poll: boolean;
}

export interface IFailedRetry {
  is_enabled: boolean;
  retry_interval: number;
  max_retry_times: number;
  timeout: number;
}

export interface IRequestBody {
  content_type: string;
  data_type: string;
  params: any[];
  content: string;
}

export interface IAuthorize {
  auth_type: string;
  auth_config: any;
}

export interface INotice {
  id: number;
  config_id: number;
  user_groups: number[];
  user_type: string;
  signal: string[];
  options: INoticeOptions;
  relate_type: string;
  config: INoticeConfig;
  is_enabled: boolean;
  is_invalid: boolean;
  invalid_type: string;
  update_time: number;
  update_user: string;
  create_time: number;
  create_user: string;
  labels: string[];
  app: string;
  path: string;
  priority: null | number;
  priority_group_key: string;
  edit_allowed: boolean;
  metric_type: string;
}

export interface INoticeOptions {
  end_time: string;
  start_time: string;
  assign_mode: string[];
  upgrade_config: IUpgradeConfig;
  converge_config: IConvergeConfig;
  chart_image_enabled: boolean;
  exclude_notice_ways: IExcludeINoticeWays;
  noise_reduce_config: INoiseReduceConfig;
}

export interface IUpgradeConfig {
  is_enabled: boolean;
  user_groups: any[];
  upgrade_interval: number;
}

export interface IExcludeINoticeWays {
  ack: any[];
  closed: any[];
  recovered: any[];
}

export interface INoiseReduceConfig {
  unit: string;
  count: number;
  timedelta: number;
  dimensions: any[];
  is_enabled: boolean;
}

export interface INoticeConfig {
  need_poll: boolean;
  notify_interval: number;
  interval_notify_mode: string;
  template: ITemplate[];
}

export interface ITemplate {
  title_tmpl: string;
  message_tmpl: string;
  signal: string;
}

export interface IAggregatedAlert {
  id: string;
  name: string;
  level_name: string;
  count: number;
  related_entities: string[];
  children: IAggregatedAlert[];
  alert_ids: string[];
  is_root: boolean;
  is_feedback_root: boolean;
  begin_time: number;
  end_time: number;
  status: string;
  alert_example: IAlertExample;
  dimension_message: string;
  metric_display: IMetricDisplay[];
  target_key: string;
  ack_operator: string;
  shield_operator: any[];
  bk_biz_name: string;
  entity: IEntity;
  isOpen: boolean;
  isShow: boolean;
  isDraw: boolean;
}

export interface IMetricDisplay {
  id: string;
  name: string;
}

export interface IEntity {
  entity_id: string;
  entity_name: string;
  entity_type: string;
  is_anomaly: boolean;
  is_root: boolean;
  rank: IRank;
  dimensions: Record<string, string>;
  anomaly_score: number;
  anomaly_type: null | string;
  is_on_alert: boolean;
  bk_biz_id: null | number;
  tags: Record<string, any>;
  aggregated_entities: any[];
}

export interface IRank {
  rank_id: number;
  rank_name: string;
  rank_alias: string;
  rank_category: IRankCategory;
}

export interface IRankCategory {
  category_id: number;
  category_name: string;
  category_alias: string;
}

export interface IAggregationRoot {
  id: string;
  name: string;
  level_name: string;
  count: number;
  related_entities: string[];
  children: IAggregatedAlert[];
  alert_ids: string[];
  is_root: boolean;
  is_feedback_root: boolean;
  begin_time: number;
  end_time: number;
  status: string;
  alert_example: IAlertExample;
  isOpen: boolean;
  isShow: boolean;
  isDraw: boolean;
}
