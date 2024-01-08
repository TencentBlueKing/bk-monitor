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

// 订阅详情 对象 开始
export type DataRange = {
  number: number;
  time_level: string;
};

export type TimeFrequency = {
  hour: number;
  type: number;
  day_list: number[];
  run_time: string;
  week_list: number[];
  data_range?: DataRange;
};

export type ScenarioConfig = {
  index_set_id: number | null;
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
  channel_name: string;
  is_enabled: boolean;
  subscribers: Subscriber[];
  send_text?: string;
};

export type Report = {
  id: number;
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
  is_self_subscribed: boolean;
  last_send_time?: null | string;
  send_status: string;
  // 该值为表单组件内的使用值，请不要上传。
  timerange?: string[];
};
// 订阅详情 对象 结束

// 生成一个有 默认数据 的对象
export function getDefaultReportData(): Report {
  return {
    id: 0,
    is_enabled: false,
    is_deleted: false,
    create_user: '',
    create_time: '1970-01-01 00:00:00+0000',
    update_user: '',
    update_time: '1970-01-01 00:00:00+0000',
    name: '',
    bk_biz_id: 0,
    scenario: 'clustering',
    frequency: {
      type: 5,
      hour: 0.5,
      day_list: [],
      run_time: '',
      week_list: [],
      data_range: null
    },
    content_config: {
      title: '',
      is_link_enabled: true
    },
    scenario_config: {
      index_set_id: 0,
      // 需要从 slider 上进行转换
      pattern_level: '01',
      log_display_count: 30,
      year_on_year_hour: 1,
      generate_attachment: true,
      // 是否只展示新类
      is_show_new_pattern: false,
      // 这个同比配置不需要前端展示，暂不开放配置入口 （不用管）
      year_on_year_change: 'all'
    },
    start_time: 0,
    end_time: 0,
    send_mode: '',
    // 给他人/仅自己 订阅，在 新增订阅 页面里强制写 others
    subscriber_type: 'others',
    send_round: 0,
    is_manager_created: false,
    channels: [
      {
        is_enabled: true,
        subscribers: [],
        channel_name: 'user'
      },
      {
        is_enabled: false,
        subscribers: [],
        send_text: '',
        channel_name: 'email'
      },
      {
        is_enabled: false,
        subscribers: [],
        channel_name: 'wxbot'
      }
    ],
    is_invalid: false,
    is_self_subscribed: false,
    last_send_time: null,
    send_status: '',
    timerange: []
  };
}
