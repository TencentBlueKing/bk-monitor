export enum FrequencyType {
  /** 按天 */
  daily = 2,
  /** 按小时 */
  hourly = 5,
  /** 按月 */
  monthly = 4,
  /** 仅一次 */
  onlyOnce = 1,
  /** 按周 */
  weekly = 3,
}

export type Channel = {
  channel_name: 'email' | 'user' | 'wxbot';
  is_enabled: boolean;
  send_text?: string;
  subscribers: Subscriber[];
};

export type ContentConfig = {
  is_link_enabled: boolean;
  title: string;
};

// 订阅详情 对象 开始
export type DataRange = {
  number: number;
  time_level: string;
};

export interface IColumn {
  field: string;
  filter?: { label: string; value: number | string }[];
  label: string;
  minWidth?: number;
  sortable?: boolean;
  width?: number | string;
}

export interface ITable {
  columns: IColumn[];
  data: Record<string, any>[];
  settings?: {
    checked: string[];
    fields: { field: string; label: string }[];
    size: string;
  };
}

export type Report = {
  bk_biz_id: number;
  channels: Channel[];
  content_config: ContentConfig;
  create_time?: string;
  create_user?: string;
  end_time: number;
  frequency: TimeFrequency;
  id: number;
  is_deleted?: boolean;
  is_enabled?: boolean;
  is_invalid?: boolean;
  is_manager_created?: boolean;
  is_self_subscribed: boolean;
  last_send_time?: null | string;
  name: string;
  scenario: string;
  scenario_config: ScenarioConfig;
  send_mode?: string;
  send_round?: number;
  send_status: string;
  start_time: number;
  subscriber_type: string;
  // 该值为表单组件内的使用值，请不要上传。
  timerange?: string[];
  update_time?: string;
  update_user?: string;
};

export type ScenarioConfig = {
  generate_attachment: boolean;
  index_set_id: null | number;
  is_show_new_pattern: boolean;
  log_display_count: number;
  pattern_level: string;
  year_on_year_change: string;
  year_on_year_hour: number;
};

export type Subscriber = {
  id: string;
  is_enabled: boolean;
  type?: string;
};
// 订阅详情 对象 结束

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

export type TimeFrequency = {
  data_range?: DataRange;
  day_list: number[];
  hour: number;
  run_time: string;
  type: FrequencyType;
  week_list: number[];
};
