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

import { IssuePriorityEnum, IssueStatusEnum } from '../constant';

import type { IssueItem, IssuePriorityType, IssueStatusType } from '../typing';

/** 模拟用户名列表 */
const MOCK_USERS = ['carmelu', 'nekzhang', 'liuwei', 'zhangsan', 'wangwu'];

/** 模拟异常信息列表 */
const MOCK_ANOMALY_MESSAGES = [
  '主机 10.0.0.1 CPU 使用率达到 95%，超过阈值 80%',
  '服务 lobby 响应超时，P99 延迟 > 5000ms',
  '数据库连接池耗尽，最大连接数 200',
  'API 网关返回 502，上游服务不可达',
  'K8S Pod CrashLoopBackOff，重启次数 > 10',
];

/** 模拟 Issue 名称列表 */
const MOCK_ISSUE_NAMES = [
  '异常登录日志告警',
  'sn.lobby服务故障引发集群lobby服务故障引发集群',
  'API网关响应超时告警',
  '内存使用率超过阈值',
  '磁盘IO延迟过高告警',
  '数据库连接池耗尽',
  'K8S Pod重启频繁',
  '服务健康检查失败',
];

/** 模拟标签组合列表 */
const MOCK_LABEL_GROUPS = [
  ['集群告警', '测试环境', 'BCS'],
  ['集群告警', '生产环境'],
  ['单机告警', 'BCS'],
  ['服务告警', '测试环境', 'K8S'],
  ['网络告警', '生产环境', 'BCS'],
];

/** 模拟策略列表 */
const MOCK_STRATEGIES = [
  { id: '1001', name: '主机 CPU 使用率过高' },
  { id: '1002', name: '服务响应超时' },
  { id: '1003', name: '数据库连接异常' },
  { id: '1004', name: 'Pod 重启频繁' },
];

/** 优先级取值列表 */
const PRIORITIES: IssuePriorityType[] = [IssuePriorityEnum.P0, IssuePriorityEnum.P1, IssuePriorityEnum.P2];

/** 状态取值列表 */
const STATUSES: IssueStatusType[] = [
  IssueStatusEnum.PENDING_REVIEW,
  IssueStatusEnum.UNRESOLVED,
  IssueStatusEnum.RESOLVED,
  IssueStatusEnum.ARCHIVED,
];

// 随机取数组元素
const randomPick = <T>(arr: T[]): T => arr[Math.floor(Math.random() * arr.length)];

// 随机生成趋势数据（[毫秒时间戳, 数量] 二元组数组）
const generateTrendData = (baseTime: number): [number, number][] => {
  const count = 12 + Math.floor(Math.random() * 12);
  return Array.from({ length: count }, (_, i) => [
    (baseTime - (count - i) * 3600) * 1000,
    Math.floor(Math.random() * 150),
  ]) as [number, number][];
};

/**
 * @description 生成模拟 Issues 数据
 * @param count - 生成数量
 * @returns IssueItem 数组
 */
export const generateMockIssues = (count = 20): IssueItem[] => {
  const now = Math.floor(Date.now() / 1000);
  return Array.from({ length: count }, (_, index) => {
    const status = STATUSES[index % STATUSES.length];
    const isResolved = status === IssueStatusEnum.RESOLVED;
    const hasPendingReview = status === IssueStatusEnum.PENDING_REVIEW;
    const assignee = hasPendingReview ? [] : [randomPick(MOCK_USERS)];
    const isRegression = index % 5 === 0;
    const strategy = randomPick(MOCK_STRATEGIES);
    const firstAlertTime = now - Math.floor(Math.random() * 86400 * 240);
    const lastAlertTime = now - Math.floor(Math.random() * 86400);
    const createTime = firstAlertTime - Math.floor(Math.random() * 3600);
    const updateTime = now - Math.floor(Math.random() * 3600);
    const resolvedTime = isResolved ? now - Math.floor(Math.random() * 86400 * 7) : null;
    const trend = generateTrendData(lastAlertTime);
    const hostCount = Math.floor(Math.random() * 10) + 1;
    const serviceCount = Math.floor(Math.random() * 5) + 1;

    return {
      id: `issue-${String(index + 1).padStart(4, '0')}`,
      name: isRegression
        ? `[回归] ${MOCK_ISSUE_NAMES[index % MOCK_ISSUE_NAMES.length]}`
        : MOCK_ISSUE_NAMES[index % MOCK_ISSUE_NAMES.length],
      status,
      status_display: { pending_review: '待审核', unresolved: '未解决', resolved: '已解决', archived: '归档' }[status],
      priority: PRIORITIES[index % PRIORITIES.length],
      priority_display: { P0: '高', P1: '中', P2: '低' }[PRIORITIES[index % PRIORITIES.length]],
      assignee,
      is_regression: isRegression,
      strategy_id: strategy.id,
      strategy_name: strategy.name,
      bk_biz_id: '2',
      bk_biz_name: '蓝鲸',
      labels: MOCK_LABEL_GROUPS[index % MOCK_LABEL_GROUPS.length],
      alert_count: trend.reduce((sum, item) => sum + item[1], 0),
      anomaly_message: randomPick(MOCK_ANOMALY_MESSAGES),
      trend,
      first_alert_time: firstAlertTime,
      last_alert_time: lastAlertTime,
      create_time: createTime,
      update_time: updateTime,
      resolved_time: resolvedTime,
      is_resolved: isResolved,
      duration: isResolved
        ? '3d 2h'
        : `${Math.floor((now - createTime) / 86400)}d ${Math.floor(((now - createTime) % 86400) / 3600)}h`,
      impact_scope: {
        host_count: hostCount,
        service_count: serviceCount,
        hosts: {
          label: '主机',
          items: Array.from({ length: Math.min(hostCount, 3) }, (_, i) => `10.0.0.${i + 1}`),
        },
        services: {
          label: '服务实例',
          items: Array.from({ length: Math.min(serviceCount, 3) }, (_, i) => `service-instance-${i + 1}`),
        },
      },
      aggregate_config: {
        aggregate_dimensions: ['bk_target_ip'],
        conditions: [],
        alert_levels: [1, 2],
      },
    };
  });
};
