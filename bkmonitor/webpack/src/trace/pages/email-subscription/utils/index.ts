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
import { useI18n } from 'vue-i18n';

import { type Report, FrequencyType } from '../types';

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
      // TODO：补齐类型
      type: 5,
      hour: 0.5,
      day_list: [],
      run_time: '',
      week_list: [],
      data_range: null,
    },
    content_config: {
      title: '',
      is_link_enabled: true,
    },
    scenario_config: {
      index_set_id: null,
      // 需要从 slider 上进行转换
      pattern_level: '09',
      log_display_count: 30,
      year_on_year_hour: 1,
      generate_attachment: true,
      // 是否只展示新类
      is_show_new_pattern: false,
      // 这个同比配置不需要前端展示，暂不开放配置入口 （不用管）
      year_on_year_change: 'all',
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
        channel_name: 'user',
      },
      {
        is_enabled: false,
        subscribers: [],
        send_text: '',
        channel_name: 'email',
      },
      {
        is_enabled: false,
        subscribers: [],
        channel_name: 'wxbot',
      },
    ],
    is_invalid: false,
    is_self_subscribed: false,
    last_send_time: null,
    send_status: '',
    timerange: [],
  };
}

export function getSendFrequencyText(data: Report) {
  const { t } = useI18n();
  const weekMap = [t('周一'), t('周二'), t('周三'), t('周四'), t('周五'), t('周六'), t('周日')];
  let str = '';
  if (!data?.frequency?.type) return '';
  switch (data.frequency.type) {
    case FrequencyType.onlyOnce: {
      str = t('仅一次');
      break;
    }
    case FrequencyType.daily: {
      const includeWeekend = [1, 2, 3, 4, 5, 6, 7];
      const isIncludeWeekend = includeWeekend.every(item => data.frequency.week_list.includes(item));
      str = `${t('每天')}${isIncludeWeekend ? `(${t('包含周末')})` : ''} ${data.frequency.run_time}`;
      break;
    }
    case FrequencyType.weekly: {
      const weekStrArr = data.frequency.week_list.map(item => weekMap[item - 1]);
      const weekStr = weekStrArr.join(', ');
      str = `${weekStr} ${data.frequency.run_time}`;
      break;
    }
    case FrequencyType.monthly: {
      const dayArr = data.frequency.day_list.map(item => `${item}号`);
      const dayStr = dayArr.join(', ');
      str = `${dayStr} ${data.frequency.run_time}`;
      break;
    }
    case FrequencyType.hourly: {
      str = t('每{0}小时发送一次', [data.frequency.hour]);
      break;
    }
    default:
      str = data.frequency.run_time;
      break;
  }
  return str;
}

/**
 * 由于 getDefaultReportData() 中包含全量的 key ，其中有一些 key 不需要在创建订阅时提交。
 * 这里会先把创建订阅无关的 key 先删掉。
 */
export function switchReportDataForCreate(data: Report) {
  // 这里只取需要的
  /* eslint-disable */
  const {
    scenario,
    name,
    start_time,
    end_time,
    subscriber_type,
    scenario_config,
    frequency,
    content_config,
    channels,
  } = data;
  /* eslint-enable */
  return {
    scenario,
    name,
    start_time,
    end_time,
    subscriber_type,
    scenario_config,
    frequency,
    content_config,
    channels,
  };
}

/**
 * 由于 getDefaultReportData() 中包含全量的 key ，其中有一些 key 不需要在更新订阅时提交。
 * 这里会先把更新订阅无关的 key 先删掉。
 */
export function switchReportDataForUpdate(data: Report) {
  // 这里只取需要的
  /* eslint-disable */
  const {
    id,
    bk_biz_id,
    is_enabled,
    scenario,
    name,
    start_time,
    end_time,
    subscriber_type,
    scenario_config,
    frequency,
    content_config,
    channels,
  } = data;
  /* eslint-enable */
  return {
    id,
    bk_biz_id,
    is_enabled,
    scenario,
    name,
    start_time,
    end_time,
    subscriber_type,
    scenario_config,
    frequency,
    content_config,
    channels,
  };
}
