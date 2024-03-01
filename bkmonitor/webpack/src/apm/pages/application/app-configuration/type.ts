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
/* eslint-disable camelcase */

import { INodeType, TargetObjectType } from 'monitor-pc/components/monitor-ip-selector/typing';
import { IPanelModel } from 'monitor-ui/chart-plugins/typings';

export interface IApdexConfig {
  apdex_default: number;
  apdex_http: number;
  apdex_db: number;
  apdex_rpc: number;
  apdex_backend: number;
  apdex_messaging: number;
}

export interface ISamplingRule {
  key: string;
  method: string;
  value: any;
  key_alias: string;
  condition?: string;
  type: string;
}

export interface IApplicationSamplerConfig {
  sampler_type: string;
  sampler_percentage?: number;
  tail_conditions: ISamplingRule[];
}

export interface IApplicationInstanceNameConfig {
  instance_name_composition: IInstanceOption[];
}

export interface IInstanceOption {
  id: string;
  name: string;
  value: string;
  alias: string;
}

export interface IDatasourceConfig {
  es_number_of_replicas: number;
  es_retention: number;
  es_storage_cluster: number;
  es_shards: number;
  es_slice_size?: number;
}

export interface INoticeGroupItem {
  id: number;
  name: string;
}

export interface IClusterConfig {
  cluster_id: number;
  cluster_name: string;
}

export interface IFormatsItem {
  id: string;
  name: string;
  suffix: string;
}

// 指标维度
export interface IDimensionItem {
  description: string;
  field_name: string;
  type: string;
  unit: string;
}

// 应用详情
export interface IAppInfo {
  application_id: number;
  app_name: string;
  app_alias: string;
  description: string;
  enable_profiling: boolean;
  enable_tracing: boolean;
  application_apdex_config: IApdexConfig;
  owner: string;
  is_enabled: boolean;
  is_enabled_profiling: boolean;
  es_storage_index_name: string;
  application_datasource_config: IDatasourceConfig;
  create_user: string;
  create_time: string;
  update_time: string;
  update_user: string;
  no_data_period: number;
  application_sampler_config: IApplicationSamplerConfig;
  application_instance_name_config: IApplicationInstanceNameConfig;
  application_db_config: {
    db_system: string;
    trace_mode: 'origin' | 'no_parameters' | 'closed';
    length: number;
    threshold: number;
    enabled_slow_sql: boolean;
  }[];
  application_db_system: string[];
  plugin_id: string;
  plugin_config?: {
    target_node_type: INodeType;
    target_object_type: TargetObjectType;
    target_nodes: any[];
    data_encoding: string;
    paths: string[];
    bk_biz_id?: number | string;
    bk_data_id?: number | string;
    subscription_id?: number | string;
  };
}

export interface ClusterOption {
  id: string;
  name: string;
}

export interface IMenuItem {
  id: string;
  name: string;
}

// 无数据告警
export interface IStrategyData {
  id: number;
  name: string;
  alert_status: number;
  alert_graph: IPanelModel;
  is_enabled: boolean;
  notice_group: INoticeGroupItem[];
}

// 指标详情
export interface IMetricData {
  field_name: string;
  metric_display_name: string;
  type: string;
  unit: string;
  table_id: string;
  data_source_label: string;
  result_table_label_name: string;
  tag_list: IDimensionItem[];
  tags: string[];
}

export interface IClusterItem {
  cluster_config: IClusterConfig;
}

export interface IndicesItem {
  health: string;
  pri: number;
  rep: number;
  docs_count: number;
  store_size: number;
}

export interface IFieldItem {
  field_name: string;
  ch_field_name: string;
  field_type: string;
  time_field: number;
  analysis_field: number;
}

export interface IUnitItme {
  name: string;
  formats: IFormatsItem[];
}

export interface IFieldFilterItem {
  text: string;
  value: string | boolean | number;
}

export interface IMatchCount {
  value: number;
}

export interface IConditionInfo {
  operator: string;
  value: string;
}

export interface IParamItem {
  name: string;
  operator: string;
  value: string;
}

export interface IRules {
  regex: string;
  operator: IConditionInfo;
  uri: IConditionInfo;
  params: IParamItem[];
}

export interface ICustomServiceInfo {
  id: number;
  name: string;
  icon: string;
  type: string;
  match_type: string;
  host_match_count: IMatchCount;
  uri_match_count: IMatchCount;
  uriMatch: number;
  rule: IRules;
}
