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
 * documentation files (the "Software", to deal in the Software without restriction, including without limitation
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

import { LANGUAGE_COOKIE_KEY, docCookies } from 'monitor-common/utils';

/**
 * @description 在关注人里面但不在通知人则禁用操作
 * @param follower
 * @param assignee
 */
export function getOperatorDisabled(follower: string[], assignee: string[]) {
  const username = window.user_name || window.username;
  const hasFollower = (follower || []).some(u => u === username);
  const hasAssignee = (assignee || []).some(u => u === username);
  return hasAssignee ? false : hasFollower;
}

const isEn = docCookies.getItem(LANGUAGE_COOKIE_KEY) === 'en';

// 告警事件告警状态筛选区域初始化数据
export const INIT_COMMON_FILTER_DATA = [
  {
    id: 'alert',
    name: isEn ? 'Alarm' : '告警',
    count: 0,
    children: [
      {
        id: 'MINE',
        name: isEn ? 'My Alarm' : '我的告警',
        count: 0,
      },
      {
        id: 'MY_APPOINTEE',
        name: isEn ? 'My Assigned' : '我负责的',
        count: 0,
      },
      {
        id: 'MY_FOLLOW',
        name: isEn ? 'My Followed' : '我关注的',
        count: 0,
      },
      {
        id: 'MY_ASSIGNEE',
        name: isEn ? 'My Received' : '我收到的',
        count: 0,
      },
      {
        id: 'NOT_SHIELDED_ABNORMAL',
        name: isEn ? 'Not Recovered' : '未恢复',
        count: 0,
      },
      {
        id: 'SHIELDED_ABNORMAL',
        name: isEn ? 'Active (muted)' : '未恢复(已屏蔽)',
        count: 0,
      },
      {
        id: 'RECOVERED',
        name: isEn ? 'Recovered' : '已恢复',
        count: 6186,
      },
    ],
    zhId: '',
  },
  {
    id: 'action',
    name: isEn ? 'Action' : '处理记录',
    count: 0,
    children: [
      {
        id: 'success',
        name: isEn ? 'Success' : '成功',
        count: 0,
      },
      {
        id: 'failure',
        name: isEn ? 'Failure' : '失败',
        count: 0,
      },
    ],
    zhId: '',
  },
];
// 告警建议字段列表
export const ALERT_FIELD_LIST = [
  {
    id: 'id',
    name: isEn ? 'Alarm ID' : '告警ID',
    zhId: '告警ID',
  },
  {
    id: 'alert_name',
    name: isEn ? 'Alarm Name' : '告警名称',
    zhId: '告警名称',
  },
  {
    id: 'status',
    name: isEn ? 'Status' : '状态',
    zhId: '状态',
  },
  {
    id: 'description',
    name: isEn ? 'Alarm Content' : '告警内容',
    zhId: '告警内容',
  },
  {
    id: 'severity',
    name: isEn ? 'Severity' : '级别',
    zhId: '级别',
  },
  {
    id: 'metric',
    name: isEn ? 'Metric ID' : '指标ID',
    zhId: '指标ID',
  },
  {
    id: 'ip',
    name: isEn ? 'Target IP' : '目标IP',
    zhId: '目标IP',
  },
  {
    id: 'ipv6',
    name: isEn ? 'Target IPv6' : '目标IPv6',
    zhId: '目标IPv6',
  },
  {
    id: 'bk_host_id',
    name: isEn ? 'Host ID' : '主机ID',
    zhId: '主机ID',
  },
  {
    id: 'bk_cloud_id',
    name: isEn ? 'Target BK-Network Area ID' : '目标云区域ID',
    zhId: '目标云区域ID',
  },
  {
    id: 'bk_service_instance_id',
    name: isEn ? 'Target Instance ID' : '目标服务实例ID',
    zhId: '目标服务实例ID',
  },
  {
    id: 'appointee',
    name: isEn ? 'Owner' : '负责人',
    zhId: '负责人',
  },
  {
    id: 'assignee',
    name: isEn ? 'Notified Person' : '通知人',
    zhId: '通知人',
  },
  {
    id: 'follower',
    name: isEn ? 'Follower' : '关注人',
    zhId: '关注人',
  },
  {
    id: 'strategy_name',
    name: isEn ? 'Rule Name' : '策略名称',
    zhId: '策略名称',
  },
  {
    id: 'strategy_id',
    name: isEn ? 'Rule ID' : '策略ID',
    zhId: '策略ID',
  },
  {
    id: 'labels',
    name: isEn ? 'Rule Label' : '策略标签',
    zhId: '策略标签',
  },
  {
    id: 'tags',
    name: isEn ? 'Dimension' : '维度',
    special: true,
    zhId: '维度',
  },
  {
    id: 'action_id',
    name: isEn ? 'Handling Record ID' : '处理记录ID',
    zhId: '处理记录ID',
  },
  {
    id: 'plugin_id',
    name: isEn ? 'Alarm Source' : '告警来源',
    zhId: '告警来源',
  },
  {
    id: 'stage',
    name: isEn ? 'Hand Stage' : '处理阶段',
    zhId: '处理阶段',
  },
];
// 故障字段列表
export const INCIDENT_FIELD_LIST = [
  {
    id: 'id',
    name: isEn ? 'Incident ID' : '故障ID',
    zhId: '故障ID',
  },
  {
    id: 'incident_name',
    name: isEn ? 'Incident Name' : '故障名称',
    zhId: '故障名称',
  },
  {
    id: 'incident_reason',
    name: isEn ? 'Incident Reason' : '故障原因',
    zhId: '故障原因',
  },
  {
    id: 'bk_biz_id',
    name: isEn ? 'Business ID' : '业务ID',
    zhId: '业务ID',
  },
  {
    id: 'status',
    name: isEn ? 'Incident Status' : '故障状态',
    zhId: '故障状态',
  },
  {
    id: 'level',
    name: isEn ? 'Incident Level' : '故障级别',
    zhId: '故障级别',
  },
  {
    id: 'assignees',
    name: isEn ? 'Owner' : '负责人',
    zhId: '负责人',
  },
  {
    id: 'handlers',
    name: isEn ? 'Handler' : '处理人',
    zhId: '处理人',
  },
  {
    id: 'labels',
    name: isEn ? 'Tag' : '标签',
    zhId: '标签',
  },
  {
    id: 'create_time',
    name: isEn ? 'Incident Detection Time' : '故障检出时间',
    zhId: '故障检出时间',
  },
  {
    id: 'update_time',
    name: isEn ? 'Incident Update Time' : '故障更新时间',
    zhId: '故障更新时间',
  },
  {
    id: 'begin_time',
    name: isEn ? 'Incident Start Time' : '故障开始时间',
    zhId: '故障开始时间',
  },
  {
    id: 'end_time',
    name: isEn ? 'Incident End Time' : '故障结束时间',
    zhId: '故障结束时间',
  },
  {
    id: 'snapshot',
    name: isEn ? 'Incident Topology Snapshot' : '故障图谱快照',
    zhId: '故障图谱快照',
  },
];
// 事件建议字段列表
export const EVENT_FIELD_LIST = [
  {
    id: 'id',
    name: isEn ? 'Global Event ID' : '全局事件ID',
    zhId: '全局事件ID',
  },
  {
    id: 'event_id',
    name: isEn ? 'Event ID' : '事件ID',
    zhId: '事件ID',
  },
  {
    id: 'plugin_id',
    name: isEn ? 'Plugin ID' : '插件ID',
    zhId: '插件ID',
  },
  {
    id: 'alert_name',
    name: isEn ? 'Alarm Name' : '告警名称',
    zhId: '告警名称',
  },
  {
    id: 'status',
    name: isEn ? 'Status' : '状态',
    zhId: '状态',
  },
  {
    id: 'description',
    name: isEn ? 'Description' : '描述',
    zhId: '描述',
  },
  {
    id: 'severity',
    name: isEn ? 'Severity' : '级别',
    zhId: '级别',
  },
  {
    id: 'metric',
    name: isEn ? 'Metric ID' : '指标ID',
    zhId: '指标ID',
  },
  {
    id: 'assignee',
    name: isEn ? 'Owner' : '负责人',
    zhId: '负责人',
  },
  {
    id: 'strategy_name',
    name: isEn ? 'Rule Name' : '策略名称',
    zhId: '策略名称',
  },
  {
    id: 'strategy_id',
    name: isEn ? 'Rule ID' : '策略ID',
    zhId: '策略ID',
  },
  {
    id: 'target_type',
    name: isEn ? 'Target Type' : '目标类型',
    zhId: '目标类型',
  },
  {
    id: 'target',
    name: isEn ? 'Target' : '目标',
    zhId: '目标',
  },
  {
    id: 'category',
    name: isEn ? 'Category' : '分类',
    zhId: '分类',
  },
];
// 处理记录建议字段列表
export const ACTION_FIELD_LIST = [
  {
    id: 'id',
    name: isEn ? 'Handling Record ID' : '处理记录ID',
    zhId: '处理记录ID',
  },
  {
    id: 'action_name',
    name: isEn ? 'Solution Name' : '套餐名称',
    zhId: '套餐名称',
  },
  {
    id: 'action_config_id',
    name: isEn ? 'Solution ID' : '套餐ID',
    zhId: '套餐ID',
  },
  {
    id: 'strategy_name',
    name: isEn ? 'Rule Name' : '策略名称',
    zhId: '策略名称',
  },
  {
    id: 'alerts',
    name: isEn ? 'Composite' : '关联告警',
    zhId: '关联告警',
  },
  {
    id: 'status',
    name: isEn ? 'Status' : '状态',
    zhId: '状态',
  },
  {
    id: 'bk_biz_name',
    name: isEn ? 'Business Name' : '业务名',
    zhId: '业务名',
  },
  {
    id: 'bk_biz_id',
    name: isEn ? 'Business ID' : '业务ID',
    zhId: '业务ID',
  },
  {
    id: 'operate_target_string',
    name: isEn ? 'Execution object' : '执行对象',
    zhId: '执行对象',
  },
  {
    id: 'action_plugin_type',
    name: isEn ? 'Solution Type' : '套餐类型',
    zhId: '套餐类型',
  },
  {
    id: 'operator',
    name: isEn ? 'Owner' : '负责人',
    zhId: '负责人',
  },
  {
    id: 'create_time',
    name: isEn ? 'Start Time' : '开始时间',
    zhId: '开始时间',
  },
  {
    id: 'end_time',
    name: isEn ? 'End Time' : '结束时间',
    zhId: '结束时间',
  },
];
