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

export interface IActionConfig {
  app: string;
  bk_biz_id: number;
  create_time: string;
  create_user: string;
  desc: string;
  execute_config: IExecuteConfig;
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
}

export interface IActionDetail {
  action_config: IActionConfig;
  action_config_id: number;
  action_name: string;
  action_plugin: IActionPlugin;
  action_plugin_type: string;
  action_plugin_type_display: string;
  alert_id: string[];
  alert_level: number;
  bk_biz_id: string;
  bk_biz_name: string;
  bk_module_ids: null;
  bk_module_names: null;
  bk_set_ids: null;
  bk_set_names: null;
  bk_target_display: string;
  content: IContent;
  converge_count: number;
  converge_id: number;
  create_time: number;
  dimension_string: string;
  dimensions: null;
  duration: string;
  end_time: number;
  ex_data: IExData;
  execute_times: number;
  failure_type: string;
  id: string;
  inputs: IInputs;
  is_converge_primary: boolean;
  is_parent_action: boolean;
  operate_target_string: string;
  operator: string[];
  outputs: IOutputs;
  parent_action_id: number;
  raw_id: number;
  related_action_ids: null;
  signal: string;
  signal_display: string;
  status: string;
  status_tips: string[];
  strategy_id: number;
  strategy_name: string;
  update_time: number;
}

export interface IActionPlugin {
  backend_config: IBackendConfig[];
  config_schema: IConfigSchema;
  id: number;
  is_enabled: boolean;
  name: string;
  plugin_key: string;
  plugin_type: string;
  update_time: string;
  update_user: string;
}

export interface IBackendConfig {
  function: string;
  name: string;
}

export interface IConfigSchema {
  content_template: string;
  content_template_shielded: string;
  content_template_shielded_with_url: string;
  content_template_with_url: string;
  content_template_without_assignee: string;
}

export interface IContent {
  action_plugin_type: string;
  text: string;
  url: string;
}

export interface IExData {
  message: string[];
}

export interface IExecuteConfig {
  template_detail: ITemplateDetail;
}

export interface IInputs {
  alert_latest_time: number;
  followed: boolean;
  is_alert_shielded: boolean;
  is_unshielded: boolean;
  mention_users: IMentionUsers;
  notice_receiver: string;
  notice_type: string;
  notice_way: string;
  notify_info: INotifyInfo;
  shield_detail: string;
  time_range: string;
}

export interface IMentionUsers {
  [key: number | string]: string[];
}

export interface INotifyInfo {
  [key: string]: string[];
}

export interface IOutputs {
  message: string;
  title: string;
}

export interface ITemplate {
  message_tmpl: string;
  signal: string;
  title_tmpl: string;
}

export interface ITemplateDetail {
  interval_notify_mode: string;
  need_poll: boolean;
  notify_interval: number;
  template: ITemplate[];
}

export class ActionDetail {
  readonly action_config: IActionConfig;
  readonly action_config_id: number;
  readonly action_name: string;
  readonly action_plugin: IActionPlugin;
  readonly action_plugin_type: string;
  readonly action_plugin_type_display: string;
  readonly alert_id: string[];
  readonly alert_level: number;
  readonly bk_biz_id: string;
  readonly bk_biz_name: string;
  readonly bk_module_ids: null;
  readonly bk_module_names: null;
  readonly bk_set_ids: null;
  readonly bk_set_names: null;
  readonly bk_target_display: string;
  readonly content: IContent;
  readonly converge_count: number;
  readonly converge_id: number;
  readonly create_time: number;
  readonly dimension_string: string;
  readonly dimensions: null;
  readonly duration: string;
  readonly end_time: number;
  readonly ex_data: IExData;
  readonly execute_times: number;
  readonly failure_type: string;
  readonly id: string;
  readonly inputs: IInputs;
  readonly is_converge_primary: boolean;
  readonly is_parent_action: boolean;
  readonly operate_target_string: string;
  readonly operator: string[];
  readonly outputs: IOutputs;
  readonly parent_action_id: number;
  readonly raw_id: number;
  readonly related_action_ids: null;
  readonly signal: string;
  readonly signal_display: string;
  readonly status: string;
  readonly status_tips: string[];
  readonly strategy_id: number;
  readonly strategy_name: string;
  readonly update_time: number;

  constructor(public readonly rawData: IActionDetail) {
    Object.assign(this, rawData);
  }
}
