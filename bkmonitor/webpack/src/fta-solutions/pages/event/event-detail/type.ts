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

export interface IDetail {
  alert_info: any;
  alert_name: string; // 告警名称
  appointee?: string[];
  assignee?: string[];
  begin_time: number; // 事件产生事件
  bk_biz_id: number; // 业务id
  bk_cloud_id?: number;
  category?: string;
  category_display?: string;
  create_time?: number;
  description: string;
  dimension: Array<{ key: string; value: string }>; // 维度信息
  dimension_message: string; // 维度信息
  dimensions?: any[];
  duration: string; // 持续时间
  end_time?: number;
  extra_info?: any;
  first_anomaly_time: number; // 首次异常事件
  follower?: string[];
  graph_panel?: any;
  id: string; // 告警id
  ip?: string;
  is_ack: boolean; // 是否确认
  is_handled: boolean;
  is_shielded: boolean; // 是否屏蔽
  latest_time?: number;
  metric?: string;
  overview?: any;
  plugin_display_name?: string; // 告警来源
  plugin_id?: string; // 告警来源ID
  relation_info?: string;
  severity: number; // 严重程度
  shield_id?: number[];
  shield_left_time?: string; // 屏蔽剩余时间
  stage_display?: string; // 处理阶段
  start_time?: number;
  status: string; // 告警状态
  strategy_id?: number;
  strategy_name?: string;
  tags?: Array<{ key: string; value: string }>;
  target?: string;
  target_type?: string;
  update_time?: number;
  extend_info?:
    | any
    | {
        result_table_id?: string;
      };
}

export const setBizIdToPanel = (panels, bkBizId) =>
  panels.map(item => {
    if (item.type === 'row') {
      if (item.panels) {
        return {
          ...item,
          panels: item.panels.map(p => ({
            ...p,
            bk_biz_id: bkBizId,
          })),
        };
      }
      return item;
    }
    return {
      ...item,
      bk_biz_id: bkBizId,
    };
  });

/* 处理记录执行状态 */

export const getStatusInfo = (status: string, failureType?: string) => {
  const statusMap = {
    success: window.i18n.tc('成功'),
    failure: window.i18n.tc('失败'),
    running: window.i18n.tc('执行中'),
    shield: window.i18n.tc('已屏蔽'),
    skipped: window.i18n.tc('被收敛'),
    framework_code_failure: window.i18n.tc('系统异常'),
    timeout: window.i18n.tc('执行超时'),
    execute_failure: window.i18n.tc('执行失败'),
    unknown: window.i18n.tc('失败'),
  };
  let text = statusMap[status];
  if (status === 'failure') {
    text = statusMap[failureType] || window.i18n.tc('失败');
  }
  return {
    status,
    text,
  };
};
