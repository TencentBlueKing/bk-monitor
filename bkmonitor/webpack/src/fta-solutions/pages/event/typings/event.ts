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
import { TranslateResult } from 'vue-i18n';

export interface ICommonTreeItem {
  id: string | SearchType;
  name: string;
  count?: number;
  children?: ICommonTreeItem[];
}

export interface ICommonItem {
  id: string;
  name: string | TranslateResult;
}

export interface IDimensionItem {
  value: string;
  key: string;
  display_value: string;
  display_key: string;
}
export interface IEventItem {
  alert_name: string;
  assignee: string[];
  begin_time: number;
  bk_biz_id: number;
  bizName: string;
  bk_cloud_id: number;
  bk_service_instance_id: string;
  category: string;
  create_time: number;
  dedupe_keys: string[];
  dedupe_md5: string;
  description: string;
  dimension_message: string;
  dimensions: IDimensionItem[];
  duration: string;
  end_time: number;
  first_anomaly_time: number;
  id: string;
  ip: string;
  is_ack: boolean;
  is_shielded: boolean;
  is_handled: boolean;
  latest_time: number;
  metric: string;
  metric_display: { id: string; name: string }[];
  seq_id: number;
  severity: number;
  status: string;
  strategy_id: number;
  tags: IDimensionItem[];
  target: string;
  target_type: string;
  update_time: number;
  extend_info?: Record<string, any>;
  event_count?: number;
  alert_count?: number;
  alert_id?: string[];
  stage_display: string;
  content: any;
  operator?: string[];
  converge_id?: number;
  converge_count?: number;
  strategy_name?: string;
  appointee?: string[];
  labels?: string[];
  shield_operator?: string[];
  ack_operator?: string;
  failure_type?: string;
  follower?: string[];
  followerDisabled?: boolean;
}

export interface IPagination {
  current: number;
  count: number;
  limit: number;
}

export interface IChatGroupDialogOptions {
  show: boolean;
  isBatch?: boolean;
  alertName?: string;
  alertCount?: number;
  assignee: string[];
  alertIds?: string[];
}

export type SearchType = 'event' | 'alert' | 'action';
export type FilterInputStatus = 'success' | 'error';
export type anlyzeChartType = 'process' | 'pie';
export type eventPanelType = 'list' | 'analyze';

export type AnlyzeField =
  | 'alert_name'
  | 'metric'
  | 'duration'
  | 'ip'
  | 'bk_cloud_id'
  | 'strategy_id'
  | 'assignee'
  | 'bk_service_instance_id'
  | 'ipv6'
  | 'plugin_id';
export type ActionAnlyzeField =
  | 'action_name'
  | 'strategy_name'
  | 'operator'
  | 'action_plugin_type'
  | 'operate_target_string'
  | 'duration';
export enum EBatchAction {
  quickShield = 'shield',
  alarmConfirm = 'ack',
  alarmDispatch = 'dispatch'
}
