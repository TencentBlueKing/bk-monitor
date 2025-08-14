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

import type { TranslateResult } from 'vue-i18n';

export enum EBatchAction {
  alarmConfirm = 'ack',
  alarmDispatch = 'dispatch',
  quickShield = 'shield',
}

export type ActionAnlyzeField =
  | 'action_name'
  | 'action_plugin_type'
  | 'duration'
  | 'operate_target_string'
  | 'operator'
  | 'strategy_name';

export type anlyzeChartType = 'pie' | 'process';
export type AnlyzeField =
  | 'alert_name'
  | 'assignee'
  | 'bk_cloud_id'
  | 'bk_service_instance_id'
  | 'duration'
  | 'ip'
  | 'ipv6'
  | 'metric'
  | 'plugin_id'
  | 'strategy_id';

export type eventPanelType = 'analyze' | 'list';

export type FilterInputStatus = 'error' | 'success';

export interface IChatGroupDialogOptions {
  alertCount?: number;
  alertIds?: string[];
  alertName?: string;
  assignee: string[];
  isBatch?: boolean;
  show: boolean;
}
export interface ICommonItem {
  id: string;
  name: string | TranslateResult;
}
export interface ICommonTreeItem {
  children?: ICommonTreeItem[];
  count?: number;
  id: SearchType | string;
  name: string;
}
export interface IDimensionItem {
  display_key: string;
  display_value: string;
  key: string;
  value: string;
}

export interface IEventItem {
  ack_operator?: string;
  alert_count?: number;
  alert_id?: string[];
  alert_name: string;
  appointee?: string[];
  assignee: string[];
  begin_time: number;
  bizName: string;
  bk_biz_id: number;
  bk_biz_name: string;
  bk_cloud_id: number;
  bk_service_instance_id: string;
  category: string;
  content: any;
  converge_count?: number;
  converge_id?: number;
  create_time: number;
  dedupe_keys: string[];
  dedupe_md5: string;
  description: string;
  dimension_message: string;
  dimensions: IDimensionItem[];
  duration: string;
  end_time: number;
  event_count?: number;
  extend_info?: Record<string, any>;
  failure_type?: string;
  first_anomaly_time: number;
  follower?: string[];
  followerDisabled?: boolean;
  id: string;
  ip: string;
  is_ack: boolean;
  is_handled: boolean;
  is_shielded: boolean;
  labels?: string[];
  latest_time: number;
  metric: string;
  metric_display: { id: string; name: string }[];
  operator?: string[];
  seq_id: number;
  severity: number;
  shield_operator?: string[];
  stage_display: string;
  status: string;
  strategy_id: number;
  strategy_name?: string;
  tags: IDimensionItem[];
  target: string;
  target_type: string;
  update_time: number;
}
export interface IPagination {
  count: number;
  current: number;
  limit: number;
}
export type SearchType = 'action' | 'alert' | 'event' | 'incident';
