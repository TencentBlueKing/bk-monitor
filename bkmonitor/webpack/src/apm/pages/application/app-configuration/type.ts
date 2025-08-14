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

import type { INodeType, TargetObjectType } from 'monitor-pc/components/monitor-ip-selector/typing';
import type { IPanelModel } from 'monitor-ui/chart-plugins/typings';

/* telemetry_data_type 字段枚举 */
export enum ETelemetryDataType {
  log = 'log',
  metric = 'metric',
  profiling = 'profiling',
  trace = 'trace',
}

export interface ClusterOption {
  id: string;
  name: string;
}

export interface IApdexConfig {
  apdex_backend: number;
  apdex_db: number;
  apdex_default: number;
  apdex_http: number;
  apdex_messaging: number;
  apdex_rpc: number;
}

// 应用详情
export interface IAppInfo {
  app_alias: string;
  app_name: string;
  application_apdex_config: IApdexConfig;
  application_datasource_config: IDatasourceConfig;
  application_db_system: string[];
  application_id: number;
  application_instance_name_config: IApplicationInstanceNameConfig;
  application_sampler_config: IApplicationSamplerConfig;
  create_time: string;
  create_user: string;
  description: string;
  enable_profiling: boolean;
  enable_tracing: boolean;
  es_storage_index_name: string;
  is_enabled: boolean;
  // 数据上报开关
  is_enabled_log: boolean;
  is_enabled_metric: boolean;
  is_enabled_profiling: boolean;
  is_enabled_trace: boolean;
  log_data_status: TDataStatus;
  // 类型状态
  metric_data_status: TDataStatus;
  no_data_period: number;
  owner: string;
  plugin_id: string;
  profiling_data_status: TDataStatus;
  trace_data_status: TDataStatus;
  update_time: string;
  update_user: string;
  application_db_config: {
    db_system: string;
    enabled_slow_sql: boolean;
    length: number;
    threshold: number;
    trace_mode: 'closed' | 'no_parameters' | 'origin';
  }[];
  plugin_config?: {
    bk_biz_id?: number | string;
    bk_data_id?: number | string;
    data_encoding: string;
    paths: string[];
    subscription_id?: number | string;
    target_node_type: INodeType;
    target_nodes: any[];
    target_object_type: TargetObjectType;
  };
}

export interface IApplicationInstanceNameConfig {
  instance_name_composition: IInstanceOption[];
}

export interface IApplicationSamplerConfig {
  sampler_percentage?: number;
  sampler_type: string;
  tail_conditions: ISamplingRule[];
}

export interface IClusterConfig {
  cluster_id: number;
  cluster_name: string;
  storage_cluster_id: string;
}

export interface IClusterItem {
  cluster_config: IClusterConfig;
}

export interface IConditionInfo {
  operator: string;
  value: string;
}

export interface ICustomServiceInfo {
  host_match_count: IMatchCount;
  icon: string;
  id: number;
  match_type: string;
  name: string;
  rule: IRules;
  type: string;
  uri_match_count: IMatchCount;
  uriMatch: number;
}
export interface IDatasourceConfig {
  es_number_of_replicas: number;
  es_retention: number;
  es_shards: number;
  es_slice_size?: number;
  es_storage_cluster: number;
}
// 指标维度
export interface IDimensionItem {
  description: string;
  field_name: string;
  type: string;
  unit: string;
}

export interface IFieldFilterItem {
  text: string;
  value: boolean | number | string;
}

export interface IFieldItem {
  analysis_field: number;
  ch_field_name: string;
  field_name: string;
  field_type: string;
  time_field: number;
}

export interface IFormatsItem {
  id: string;
  name: string;
  suffix: string;
}

export interface IInstanceOption {
  alias: string;
  id: string;
  name: string;
  value: string;
}

export interface ILogStorageInfo {
  display_es_storage_index_name: string;
  display_index_split_rule: string;
  display_storage_cluster_name: string;
  es_number_of_replicas: number;
  es_retention: number;
  es_shards: number;
  es_slice_size: number;
  es_storage_cluster: number;
}

export interface IMatchCount {
  value: number;
}

export interface IMenuItem {
  id: string;
  name: string;
}

// 指标详情
export interface IMetricData {
  data_source_label: string;
  field_name: string;
  metric_display_name: string;
  result_table_label_name: string;
  table_id: string;
  tag_list: IDimensionItem[];
  tags: string[];
  type: string;
  unit: string;
}
/* 存储状态 指标 存储信息 */
export interface IMetricStorageInfo {
  created_at: string;
  created_by: string;
  expire_time_alias: string;
  result_table_id: string;
  status: 'failed' | 'running' | 'started' | 'stopped';
  status_display: string;
  storage_type: string;
}

export interface IndicesItem {
  docs_count: number;
  health: string;
  pri: number;
  rep: number;
  store_size: number;
}

export interface INoticeGroupItem {
  id: number;
  name: string;
}

export interface IParamItem {
  name: string;
  operator: string;
  value: string;
}

export interface IRules {
  operator: IConditionInfo;
  params: IParamItem[];
  regex: string;
  uri: IConditionInfo;
}

export interface ISamplingRule {
  condition?: string;
  key: string;
  key_alias: string;
  method: string;
  type: string;
  value: any;
}

/* 存储信息 */
export interface IStorageInfo {
  [key: string]: ILogStorageInfo & IMetricStorageInfo[] & ITracingStorageInfo;
}

export interface IStoreItem {
  create_time: string;
  create_user: string;
  es_storage_cluster: string;
  es_storage_index_name: string;
  health: string;
  validity: string;
}
// 无数据告警
export interface IStrategyData {
  alert_graph: IPanelModel;
  alert_status: number;
  id: number;
  is_enabled: boolean;
  name: string;
  notice_group: INoticeGroupItem[];
}

/* 调用链存储信息 */
export interface ITracingStorageInfo {
  es_number_of_replicas: number;
  es_retention: number;
  es_shards: number;
  es_slice_size: number;
  es_storage_cluster: number;
}
export interface IUnitItme {
  formats: IFormatsItem[];
  name: string;
}

type TDataStatus = 'disabled' | 'no_data' | 'normal';
