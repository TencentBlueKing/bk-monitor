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

export interface AlarmData {
  access_time: number;
  detect_time: number;
  dimension_fields: string[];
  dimensions: Record<string, any>;
  record_id: string;
  time: number;
  value: number;
  values: Record<string, number>;
}

export interface Alert {
  alert_example: IAlertExample | null;
  alert_ids: string[];
  begin_time: null | number;
  children: Alert[];
  count: number;
  end_time: null | number;
  id: string;
  is_feedback_root: boolean;
  is_root: boolean;
  level_name: string;
  name: string;
  related_entities: string[];
  status: null | string;
}

export interface IAction {
  config: IActionConfig;
  config_id: number;
  id: number;
  options: IActionOptions;
  relate_type: string;
  signal: string[];
  user_groups: number[];
  user_type: string;
}

export interface IActionConfig {
  bk_biz_id: string;
  desc: string;
  execute_config: IExecuteConfig;
  id: number;
  name: string;
  plugin_id: string;
}

export interface IActionOptions {
  converge_config: IConvergeConfig;
  end_time: string;
  start_time: string;
}

export interface IAggregatedAlert {
  ack_operator: string;
  alert_example: IAlertExample;
  alert_ids: string[];
  begin_time: number;
  bk_biz_name: string;
  children: IAggregatedAlert[];
  count: number;
  dimension_message: string;
  end_time: number;
  entity: IEntity;
  id: string;
  is_feedback_root: boolean;
  is_root: boolean;
  isDraw: boolean;
  isOpen: boolean;
  isShow: boolean;
  level_name: string;
  metric_display: IMetricDisplay[];
  name: string;
  related_entities: string[];
  shield_operator: any[];
  status: string;
  target_key: string;
}

export interface IAggregationRoot {
  alert_example: IAlertExample;
  alert_ids: string[];
  begin_time: number;
  children: IAggregatedAlert[];
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
  related_entities: string[];
  status: string;
}

export interface IAlarmTrigger {
  anomaly_ids: string[];
  level: string;
}

export interface IAlertExample {
  ack_duration: number;
  alert_name: string;
  appointee: string[];
  assignee: string[];
  begin_time: number;
  bk_biz_id: number;
  bk_cloud_id: number;
  bk_host_id: number;
  bk_service_instance_id: any | null;
  bk_topo_node: string[];
  category: string;
  category_display: string;
  converge_id: string;
  create_time: number;
  data_type: string;
  dedupe_keys: string[];
  dedupe_md5: string;
  description: string;
  dimensions: IDimension[];
  duration: string;
  end_time: number;
  event_id: string;
  extra_info: IExtraInfo;
  first_anomaly_time: number;
  follower: any | null;
  id: string;
  ip: string;
  ipv6: string;
  is_ack: any | null;
  is_blocked: boolean;
  is_handled: boolean;
  is_shielded: boolean;
  labels: any | null;
  latest_time: number;
  metric: string[];
  plugin_display_name: string;
  plugin_id: string;
  seq_id: number;
  severity: number;
  shield_id: any | null;
  shield_left_time: string;
  stage_display: string;
  status: string;
  strategy_id: number;
  strategy_name: string;
  supervisor: any | null;
  tags: ITag[];
  target: string;
  target_type: string;
  update_time: number;
}

export interface IAlgorithm {
  config: any;
  id: number;
  level: number;
  type: string;
  unit_prefix: string;
}

export interface IAnomaly {
  anomaly_id: string;
  anomaly_message: string;
  anomaly_time: string;
}

export interface IAuthorize {
  auth_config: any;
  auth_type: string;
}

export interface ICondition {
  dimension: string;
  value: string[];
}

export interface IConvergeConfig {
  condition: ICondition[];
  converge_func: string;
  count: number;
  is_enabled: boolean;
  need_biz_converge: boolean;
  sub_converge_config?: ISubIConvergeConfig;
  timedelta: number;
}

export interface IDetect {
  connector: string;
  expression: string;
  id: number;
  level: number;
  recovery_config: IRecoveryConfig;
  trigger_config: ITriggerConfig;
}

export interface IDimension {
  display_key: string;
  display_value: string;
  key: string;
  value: number | string;
}

export interface IDimensionTranslation {
  bk_host_id: ITranslationValue;
  bk_target_ip: ITranslationValue;
  bk_topo_node: ITranslationValue<ITranslationNode[]>;
  device_name: ITranslationValue;
}

export interface IEntity {
  aggregated_entities: any[];
  anomaly_score: number;
  anomaly_type: null | string;
  bk_biz_id: null | number;
  dimensions: Record<string, string>;
  entity_id: string;
  entity_name: string;
  entity_type: string;
  is_anomaly: boolean;
  is_on_alert: boolean;
  is_root: boolean;
  rank: IRank;
  tags: Record<string, any>;
}

export interface IExcludeINoticeWays {
  ack: any[];
  closed: any[];
  recovered: any[];
}

export interface IExecuteConfig {
  template_detail: ITemplateDetail;
  timeout: number;
}

export interface IExtraInfo {
  origin_alarm: OriginAlarm;
  strategy: IStrategy;
}

export interface IFailedRetry {
  is_enabled: boolean;
  max_retry_times: number;
  retry_interval: number;
  timeout: number;
}

export interface IMetricDisplay {
  id: string;
  name: string;
}

export interface INoDataConfig {
  agg_dimension: string[];
  continuous: number;
  is_enabled: boolean;
  level: number;
}

export interface INoiseReduceConfig {
  count: number;
  dimensions: any[];
  is_enabled: boolean;
  timedelta: number;
  unit: string;
}

export interface INotice {
  app: string;
  config: INoticeConfig;
  config_id: number;
  create_time: number;
  create_user: string;
  edit_allowed: boolean;
  id: number;
  invalid_type: string;
  is_enabled: boolean;
  is_invalid: boolean;
  labels: string[];
  metric_type: string;
  options: INoticeOptions;
  path: string;
  priority: null | number;
  priority_group_key: string;
  relate_type: string;
  signal: string[];
  update_time: number;
  update_user: string;
  user_groups: number[];
  user_type: string;
}

export interface INoticeConfig {
  interval_notify_mode: string;
  need_poll: boolean;
  notify_interval: number;
  template: ITemplate[];
}

export interface INoticeOptions {
  assign_mode: string[];
  chart_image_enabled: boolean;
  converge_config: IConvergeConfig;
  end_time: string;
  exclude_notice_ways: IExcludeINoticeWays;
  noise_reduce_config: INoiseReduceConfig;
  start_time: string;
  upgrade_config: IUpgradeConfig;
}

export interface IQueryConfig {
  agg_condition: any[];
  agg_dimension: string[];
  agg_interval: number;
  agg_method: string;
  alias: string;
  data_source_label: string;
  data_type_label: string;
  functions: any[];
  id: number;
  metric_field: string;
  metric_id: string;
  result_table_id: string;
  unit: string;
}

export interface IRank {
  rank_alias: string;
  rank_category: IRankCategory;
  rank_id: number;
  rank_name: string;
}

export interface IRankCategory {
  category_alias: string;
  category_id: number;
  category_name: string;
}

export interface IRecoveryConfig {
  check_window: number;
  status_setter: string;
}

export interface IRequestBody {
  content: string;
  content_type: string;
  data_type: string;
  params: any[];
}

export interface IStrategy {
  actions: IAction[];
  app: string;
  bk_biz_id: number;
  create_time: number;
  create_user: string;
  detects: IDetect[];
  edit_allowed: boolean;
  id: number;
  invalid_type: string;
  is_enabled: boolean;
  is_invalid: boolean;
  items: IStrategyItem[];
  labels: string[];
  metric_type: string;
  name: string;
  notice: INotice;
  path: string;
  priority: null | number;
  priority_group_key: string;
  scenario: string;
  source: string;
  type: string;
  update_time: number;
  update_user: string;
  version: string;
}

export interface IStrategyItem {
  algorithms: IAlgorithm[];
  expression: string;
  functions: any[];
  id: number;
  metric_type: string;
  name: string;
  no_data_config: INoDataConfig;
  origin_sql: string;
  query_configs: IQueryConfig[];
  query_md5: string;
  target: any[];
  update_time: number;
}

export interface ISubIConvergeConfig {
  condition: ICondition[];
  converge_func: string;
  count: number;
  timedelta: number;
}

export interface ITag {
  key: string;
  value: string;
}

export interface ITemplate {
  message_tmpl: string;
  signal: string;
  title_tmpl: string;
}

export interface ITemplateDetail {
  authorize: IAuthorize;
  body: IRequestBody;
  failed_retry: IFailedRetry;
  headers: any[];
  method: string;
  need_poll: boolean;
  notify_interval: number;
  query_params: any[];
  url: string;
}

export interface ITimeRange {
  end: string;
  start: string;
}

export interface ITranslationNode {
  bk_inst_name: string;
  bk_obj_name: string;
}

export interface ITranslationValue<T = string> {
  display_name: string;
  display_value: T;
  value: T;
}

export interface ITriggerConfig {
  check_window: number;
  count: number;
  uptime: IUptime;
}

export interface IUpgradeConfig {
  is_enabled: boolean;
  upgrade_interval: number;
  user_groups: any[];
}

export interface IUptime {
  calendars: any[];
  time_ranges: ITimeRange[];
}

export interface OriginAlarm {
  anomaly: Record<string, IAnomaly>;
  data: AlarmData;
  dimension_translation: IDimensionTranslation;
  strategy_snapshot_key: string;
  trigger: IAlarmTrigger;
  trigger_time: number;
}
