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
/* eslint-disable @typescript-eslint/naming-convention */

import { ALARM_CENTER_PANEL_TAB_MAP, AlarmCenterPanelTabList } from '../utils/constant';

/** 聚合条件 */
export interface IAggCondition {
  _origin_method?: string;
  condition: string;
  dimension_name?: string;
  key: string;
  method: string;
  value: string[];
}

/** 聚合维度详情 */
export interface IAggDimensionDetail {
  display_name: string;
  display_value: string;
  value: string;
}

export interface IAlarmDetail {
  ack_duration: null | string;
  alert_name: string;
  appointee: string[];
  assignee: string[];
  begin_time: number;
  bk_biz_id: number;
  bk_cloud_id: null | number;
  bk_host_id: null | number;
  bk_service_instance_id: null | number;
  bk_topo_node: any | null;
  category: string;
  category_display: null | string;
  converge_id: string;
  create_time: number;
  data_type: string;
  dedupe_keys: string[];
  dedupe_md5: string;
  description: string;
  dimension_message: string;
  dimensions: IDimension[];
  duration: string;
  end_time: null | number;
  event_id: string;
  extend_info: IExtendInfo;
  extra_info: IExtraInfo;
  first_anomaly_time: number;
  follower: null | string[];
  graph_panel: IGraphPanel;
  id: string;
  ip: null | string;
  ipv6: null | string;
  is_ack: boolean | null;
  is_blocked: boolean;
  is_handled: boolean;
  is_shielded: boolean;
  items: IAlertItem[];
  labels: string[];
  latest_time: number;
  metric: string[];
  metric_display: IMetricDisplay[];
  plugin_display_name: string;
  plugin_id: string;
  relation_info: string;
  seq_id: number;
  severity: number;
  shield_id: null | number;
  shield_left_time: string;
  stage_display: string;
  status: string;
  strategy_id: number;
  strategy_name: string;
  supervisor: null | string;
  tags: ITag[];
  target?: any | null;
  target_key: string;
  target_type: string;
  update_time: number;
}

/** 告警项 */
export interface IAlertItem {
  expression: string;
  functions: any[];
  id: number;
  name: string;
  origin_sql: string;
  query_configs: IAlertItemQueryConfig[];
}

/** 告警项查询配置 */
export interface IAlertItemQueryConfig {
  agg_condition: IAggCondition[];
  agg_dimension: Record<string, IAggDimensionDetail>;
  agg_interval: number;
  agg_method: null | string;
  alias: string;
  functions: any[];
  metric_id: string;
}

/** 算法 */
export interface IAlgorithm {
  config: IAlgorithmConfigItem[][][];
  id: number;
  level: number;
  type: string;
  unit_prefix: string;
}

/** 算法配置项 */
export interface IAlgorithmConfigItem {
  method: string;
  threshold: number;
}

/** 异常信息 */
export interface IAnomalyInfo {
  anomaly_id: string;
  anomaly_message: string;
  anomaly_time: string;
}

export interface IChatGroupDialogOptions {
  alertCount?: number;
  alertIds?: string[];
  alertName?: string;
  assignee: string[];
  isBatch?: boolean;
  show: boolean;
}

/** 收敛条件 */
export interface IConvergeCondition {
  dimension: string;
  value: string[];
}

/** 收敛配置 */
export interface IConvergeConfig {
  condition: IConvergeCondition[];
  converge_func: string;
  count: number;
  is_enabled: boolean;
  need_biz_converge: boolean;
  sub_converge_config: ISubConvergeConfig;
  timedelta: number;
}

/** 周期处理记录项 */
export interface ICycleHandleRecordItem {
  execute_times: number;
  is_shielded: boolean;
  last_time: number;
  latest_anomaly_time: number;
}

/** 检测配置 */
export interface IDetect {
  connector: string;
  expression: string;
  id: number;
  level: number;
  recovery_config: IRecoveryConfig;
  trigger_config: ITriggerConfig;
}

/** 维度项 */
export interface IDimension {
  display_key: string;
  display_value: string;
  key: string;
  value: number | string;
}

/** 维度翻译 */
export interface IDimensionTranslation {
  display_name: string;
  display_value: string;
  value: string;
}

/** 扩展信息 */
export interface IExtendInfo {
  data_label: string;
  index_set_id: number;
  query_string: string;
  result_table_id: string;
  type: string;
  agg_condition: Array<{
    condition: string;
    key: string;
    method: string;
    value: string[];
  }>;
}

/** 额外信息 */
export interface IExtraInfo {
  agg_dimensions: string[];
  cycle_handle_record: Record<string, ICycleHandleRecordItem>;
  matched_rule_info: IMatchedRuleInfo;
  origin_alarm: IOriginAlarm;
  strategy: IStrategy;
}

/** 图表指标 */
export interface IGraphMetric {
  alias: string;
  field: string;
  method: string;
}

/** 图表面板 */
export interface IGraphPanel {
  id: string;
  subTitle: string;
  targets: IGraphTarget[];
  title: string;
  type: string;
}

/** 图表查询配置 */
export interface IGraphQueryConfig {
  bk_biz_id: number;
  custom_event_name: string;
  data_label: string;
  data_source_label: string;
  data_type_label: string;
  extend_fields: Record<string, any>;
  filter_dict: Record<string, any>;
  functions: any[];
  group_by: string[];
  index_set_id: number;
  interval: number;
  metrics: IGraphMetric[];
  promql: string;
  query_string: string;
  table: string;
  time_field: string;
  where: IGraphWhere[];
}

/** 图表目标 */
export interface IGraphTarget {
  alias: string;
  data: IGraphTargetData;
  datasourceId: string;
  name: string;
}

/** 图表目标数据 */
export interface IGraphTargetData {
  expression: string;
  functions: any[];
  query_configs: IGraphQueryConfig[];
  function: {
    time_compare: string[];
  };
}

/** 图表 where 条件 */
export interface IGraphWhere {
  condition?: string;
  key: string;
  method: string;
  value: string[];
}

/** 匹配规则信息 */
export interface IMatchedRuleInfo {
  additional_tags: any[];
  follow_groups: any[];
  group_info: Record<string, any>;
  itsm_actions: Record<string, any>;
  notice_appointees: any[];
  notice_upgrade_user_groups: any[];
  rule_snaps: Record<string, any>;
  severity: number;
}

/** 指标显示 */
export interface IMetricDisplay {
  id: string;
  name: string;
}

/** 无数据配置 */
export interface INoDataConfig {
  agg_dimension: string[];
  continuous: number;
  is_enabled: boolean;
  level: number;
}

/** 通知 */
export interface INotice {
  config: INoticeConfigDetail;
  config_id: number;
  id: number;
  options: INoticeOptions;
  relate_type: string;
  signal: string[];
  user_groups: number[];
  user_type: string;
}

/** 通知配置详情 */
export interface INoticeConfigDetail {
  interval_notify_mode: string;
  need_poll: boolean;
  notify_interval: number;
  template: INoticeTemplate[];
}

/** 通知选项 */
export interface INoticeOptions {
  assign_mode: string[];
  chart_image_enabled: boolean;
  converge_config: IConvergeConfig;
  end_time: string;
  exclude_notice_ways: Record<string, any>;
  noise_reduce_config: Record<string, any>;
  start_time: string;
  upgrade_config: Record<string, any>;
}

/** 通知模板 */
export interface INoticeTemplate {
  message_tmpl: string;
  signal: string;
  title_tmpl: string;
}

/** 原始告警 */
export interface IOriginAlarm {
  anomaly: Record<string, IAnomalyInfo>;
  data: IOriginAlarmData;
  dimension_translation: Record<string, IDimensionTranslation>;
  strategy_snapshot_key: string;
  trigger: IOriginAlarmTrigger;
  trigger_time: number;
}

/** 原始告警数据 */
export interface IOriginAlarmData {
  access_time: number;
  detect_time: number;
  dimension_fields: string[];
  dimensions: Record<string, string>;
  record_id: string;
  time: number;
  value: number;
  values: Record<string, number>;
}

/** 原始告警触发器 */
export interface IOriginAlarmTrigger {
  anomaly_ids: string[];
  level: string;
}

/** 查询配置 */
export interface IQueryConfig {
  agg_condition: IAggCondition[];
  agg_dimension: string[];
  agg_interval: number;
  alias: string;
  data_source_label: string;
  data_type_label: string;
  functions: any[];
  id: number;
  index_set_id: number;
  metric_field: string;
  metric_id: string;
  query_string: string;
  result_table_id: string;
  time_field: string;
}

/** 恢复配置 */
export interface IRecoveryConfig {
  check_window: number;
  status_setter: string;
}

/** 策略 */
export interface IStrategy {
  actions: any[];
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

/** 策略项 */
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
  target: any[][];
  time_delay: number;
  update_time: number;
}

/** 子收敛配置 */
export interface ISubConvergeConfig {
  condition: IConvergeCondition[];
  converge_func: string;
  count: number;
  timedelta: number;
}

/** 标签项 */
export interface ITag {
  key: string;
  value: string;
}

/** 触发配置 */
export interface ITriggerConfig {
  check_window: number;
  count: number;
  uptime: {
    active_calendars: any[];
    calendars: any[];
    time_ranges: Array<{
      end: string;
      start: string;
    }>;
  };
}

/** 告警详情类 */
export class AlarmDetail {
  readonly ack_duration: null | string;
  readonly alert_name: string;
  readonly anomaly_timestamps: number[];
  readonly appointee: string[];
  readonly assignee: string[];
  readonly begin_time: number;
  readonly bk_biz_id: number;
  readonly bk_cloud_id: null | number;
  readonly bk_host_id: null | number;
  readonly bk_service_instance_id: null | number;
  readonly bk_topo_node: any | null;
  readonly category: string;
  readonly category_display: null | string;
  readonly converge_id: string;
  readonly create_time: number;
  readonly data_type: string;
  readonly dedupe_keys: string[];
  readonly dedupe_md5: string;
  readonly description: string;
  readonly dimension_message: string;
  readonly dimensions: IDimension[];
  readonly duration: string;
  readonly end_time: null | number;
  readonly event_id: string;
  readonly extend_info: IExtendInfo;
  readonly extra_info: IExtraInfo;
  readonly first_anomaly_time: number;
  readonly follower: null | string[];
  readonly graph_panel: IGraphPanel;
  readonly id: string;
  readonly ip: null | string;
  readonly ipv6: null | string;
  readonly is_ack: boolean | null;
  readonly is_blocked: boolean;
  readonly is_handled: boolean;
  readonly is_shielded: boolean;
  readonly items: IAlertItem[];
  readonly labels: string[];
  readonly latest_time: number;
  readonly metric: string[];
  readonly metric_display: IMetricDisplay[];
  readonly plugin_display_name: string;
  readonly plugin_id: string;
  readonly relation_info: string;
  readonly seq_id: number;
  readonly severity: number;
  readonly shield_id: null | number;
  readonly shield_left_time: string;
  readonly stage_display: string;
  readonly status: 'ABNORMAL' | 'CLOSED' | 'RECOVERED';
  readonly strategy_id: number;
  readonly strategy_name: string;
  readonly supervisor: null | string;
  readonly tags: ITag[];
  readonly target?: object[];
  readonly target_key: string;
  readonly target_type: string;
  readonly update_time: number;

  constructor(public readonly rawData: IAlarmDetail) {
    Object.assign(this, rawData);
  }

  get alarmTabList() {
    return AlarmCenterPanelTabList.filter(item => {
      /* 主机和日志 */
      // if (item.name === ALARM_CENTER_PANEL_TAB_MAP.HOST || item.name === ALARM_CENTER_PANEL_TAB_MAP.LOG) {
      //   return this.dimensions?.some(item => ['bk_target_ip', 'ip'].includes(item.key));
      // }
      /* 进程 */
      if (item.name === ALARM_CENTER_PANEL_TAB_MAP.PROCESS) {
        return this.category === 'host_process' && this.dimensions?.some(item => item.key === 'tags.display_name');
      }
      /* 容器 */
      if (item.name === ALARM_CENTER_PANEL_TAB_MAP.CONTAINER) {
        return /^(APM|K8S)-\w+$/.test(this.target_type);
      }
      return true;
    });
  }
}
