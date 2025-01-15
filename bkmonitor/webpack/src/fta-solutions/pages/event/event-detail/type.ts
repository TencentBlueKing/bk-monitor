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
  id: string; // 告警id
  bk_biz_id: number; // 业务id
  alert_name: string; // 告警名称
  first_anomaly_time: number; // 首次异常事件
  begin_time: number; // 事件产生事件
  is_ack: boolean; // 是否确认
  is_shielded: boolean; // 是否屏蔽
  is_handled: boolean;
  dimension: Array<{ key: string; value: string }>; // 维度信息
  severity: number; // 严重程度
  status: string; // 告警状态
  alert_info: any;
  description: string;
  duration: string; // 持续时间
  plugin_display_name?: string; // 告警来源
  plugin_id?: string; // 告警来源ID
  dimension_message: string; // 维度信息
  extra_info?: any;
  extend_info?:
    | {
        result_table_id?: string;
      }
    | any;
  create_time?: number;
  start_time?: number;
  end_time?: number;
  update_time?: number;
  strategy_id?: number;
  category_display?: string;
  strategy_name?: string;
  metric?: string;
  tags?: Array<{ key: string; value: string }>;
  relation_info?: string;
  latest_time?: number;
  graph_panel?: any;
  target_type?: string;
  target?: string;
  ip?: string;
  bk_cloud_id?: number;
  overview?: any;
  shield_left_time?: string; // 屏蔽剩余时间
  dimensions?: any[];
  shield_id?: number[];
  category?: string;
  assignee?: string[];
  stage_display?: string; // 处理阶段
  appointee?: string[];
  follower?: string[];
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
