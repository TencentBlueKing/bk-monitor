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
export type TestSendingTarget = 'all' | 'self';

export enum FrequencyType {
  /** 按天 */
  dayly = 2,
  /** 按小时 */
  hourly = 5,
  /** 按月 */
  monthly = 4,
  /** 仅一次 */
  onlyOnce = 1,
  /** 按周 */
  weekly = 3,
}

// 订阅详情 对象 开始
export type DataRange = {
  number: number;
  time_level: string;
};

export type TimeFrequency = {
  hour: number;
  type: FrequencyType;
  day_list: number[];
  run_time: string;
  week_list: number[];
  data_range?: DataRange;
};

export type ScenarioConfig = {
  index_set_id: null | number;
  pattern_level: string;
  log_display_count: number;
  year_on_year_hour: number;
  generate_attachment: boolean;
  is_show_new_pattern: boolean;
  year_on_year_change: string;
};

export type ContentConfig = {
  title: string;
  is_link_enabled: boolean;
};

export type Subscriber = {
  id: string;
  type?: string;
  is_enabled: boolean;
};

export type Channel = {
  channel_name: 'email' | 'user' | 'wxbot';
  is_enabled: boolean;
  subscribers: Subscriber[];
  send_text?: string;
};

export type Report = {
  id?: number;
  is_enabled?: boolean;
  is_deleted?: boolean;
  create_user?: string;
  create_time?: string;
  update_user?: string;
  update_time?: string;
  name: string;
  bk_biz_id: number;
  scenario: string;
  frequency: TimeFrequency;
  content_config: ContentConfig;
  scenario_config: ScenarioConfig;
  start_time: number;
  end_time: number;
  send_mode?: string;
  subscriber_type: string;
  send_round?: number;
  is_manager_created?: boolean;
  channels: Channel[];
  is_invalid?: boolean;
  is_self_subscribed?: boolean;
  last_send_time?: null | string;
  send_status?: string;
  // 该值为表单组件内的使用值，请不要上传。
  timerange?: string[];
  // 表单的验证的 bug ，后期再考虑删掉
  scenario_config__log_display_count?: number;
  // 同上一个道理
  content_config__title?: string;
};
// 订阅详情 对象 结束
