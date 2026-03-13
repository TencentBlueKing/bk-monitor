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

import { IssuePriorityEnum, IssueStatusEnum, IssueTypeEnum } from '../constant';

import type { IssueItem, IssuePriorityType, IssueStatusType, IssueTypeType } from '../typing';

/** 模拟用户名列表 */
const MOCK_USERS = ['carmelu', 'nekzhang', 'liuwei', 'zhangsan', 'wangwu'];

/** 模拟异常类型列表 */
const MOCK_EXCEPTIONS = [
  'NullpointerException',
  'IndexOutOfBoundsExceptionIndexOutOfBoundsException',
  'TimeoutException',
  'ConnectionRefusedException',
  'IllegalArgumentException',
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
const MOCK_TAG_GROUPS = [
  ['集群告警', '测试环境', 'BCS'],
  ['集群告警', '生产环境'],
  ['单机告警', 'BCS'],
  ['服务告警', '测试环境', 'K8S'],
  ['网络告警', '生产环境', 'BCS'],
];

/** 模拟影响服务列表 */
const MOCK_SERVICES = ['zone-100012', 'lobby-753453453223...', 'gateway-10086', 'db-master-001'];

/** 优先级取值列表 */
const PRIORITIES: IssuePriorityType[] = [
  IssuePriorityEnum.HIGH,
  IssuePriorityEnum.MEDIUM,
  IssuePriorityEnum.LOW,
];

/** 状态取值列表 */
const STATUSES: IssueStatusType[] = [
  IssueStatusEnum.PENDING_REVIEW,
  IssueStatusEnum.UNRESOLVED,
  IssueStatusEnum.RESOLVED,
];

/** Issue 类型取值列表 */
const ISSUE_TYPES: IssueTypeType[] = [IssueTypeEnum.NEW, IssueTypeEnum.REGRESSION];

// 随机取数组元素
const randomPick = <T>(arr: T[]): T => arr[Math.floor(Math.random() * arr.length)];

// 随机生成趋势数据（24个柱状值）
const generateTrendData = (): number[] => Array.from({ length: 24 }, () => Math.floor(Math.random() * 150));

/**
 * @description 生成模拟 Issues 数据
 * @param count - 生成数量
 * @returns IssueItem 数组
 */
export const generateMockIssues = (count = 20): IssueItem[] => {
  const now = Math.floor(Date.now() / 1000);
  return Array.from({ length: count }, (_, index) => {
    const status = STATUSES[index % STATUSES.length];
    const hasPendingReview = status === IssueStatusEnum.PENDING_REVIEW;
    const assigneeCount = hasPendingReview ? 0 : Math.floor(Math.random() * 2) + 1;
    const assignee = hasPendingReview
      ? []
      : Array.from({ length: assigneeCount }, () => randomPick(MOCK_USERS)).filter((v, i, arr) => arr.indexOf(v) === i);

    return {
      id: `issue-${String(index + 1).padStart(4, '0')}`,
      issue_name: MOCK_ISSUE_NAMES[index % MOCK_ISSUE_NAMES.length],
      exception_type: randomPick(MOCK_EXCEPTIONS),
      issue_type: randomPick(ISSUE_TYPES),
      alert_count: Math.floor(Math.random() * 200) + 1,
      severity: [1, 2, 3][index % 3],
      tags: MOCK_TAG_GROUPS[index % MOCK_TAG_GROUPS.length],
      last_seen: now - Math.floor(Math.random() * 86400),
      first_seen: now - Math.floor(Math.random() * 86400 * 240),
      trend_data: generateTrendData(),
      impact_service: randomPick(MOCK_SERVICES),
      impact_host_count: Math.floor(Math.random() * 200) + 10,
      priority: PRIORITIES[index % PRIORITIES.length],
      status,
      assignee,
    };
  });
};
