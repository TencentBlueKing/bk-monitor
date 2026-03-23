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

import { ImpactScopeResourceKeyEnum, IssuePriorityEnum, IssueStatusEnum } from '../constant';

import type { RequestOptions } from '../../services/base';
import type { CommonFilterParams } from '../../typings';
import type {
  AssignIssuesParams,
  ImpactScope,
  IssueItem,
  IssuePriorityType,
  IssuesAssigneeDialogEvent,
  IssuesOperationDialogEvent,
  IssuesPriorityDialogEvent,
  IssuesResolveDialogEvent,
  IssueStatusType,
  ResolveIssuesParams,
  UpdatePriorityParams,
} from '../typing';

/** mock 请求参数类型 */
type MockFetchParams = CommonFilterParams & {
  show_aggs?: boolean;
  show_dsl?: boolean;
};

/** 模拟用户名列表 */
const MOCK_USERS = ['zhangsan', 'lisi', 'wangwu', 'zhaoliu', 'sunqi'];

/** 模拟异常信息列表 */
const MOCK_ANOMALY_MESSAGES = [
  '主机 192.168.1.10 CPU 使用率达到 95%，超过阈值 80%',
  '服务 demo-app 响应超时，P99 延迟 > 5000ms',
  '数据库连接池耗尽，最大连接数 200',
  'API 网关返回 502，上游服务不可达',
  'K8S Pod CrashLoopBackOff，重启次数 > 10',
];

/** 模拟 Issue 名称列表 */
const MOCK_ISSUE_NAMES = [
  '异常登录日志告警',
  'demo-app服务故障引发集群级联异常',
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

// 生成模拟影响范围数据（根据 index 模拟不同场景）
const generateMockImpactScope = (index: number): ImpactScope => {
  const scenario = index % 4;

  // 场景 0：CMDB 主机场景（set + host + service_instances）
  if (scenario === 0) {
    return {
      set: {
        count: 3,
        instance_list: [
          { set_id: '7001001', display_name: 'mock-project/bcs-demo-BCS-K8S-70001' },
          { set_id: '7001002', display_name: '示例平台/BCS-K8S-70002' },
          { set_id: '7001003', display_name: '测试数据库环境/db.mock.es' },
        ],
        link_tpl: null,
      },
      host: {
        count: 5,
        instance_list: [
          { bk_host_id: 1000001, display_name: '192.168.10.11' },
          { bk_host_id: 1000002, display_name: '192.168.10.12' },
          { bk_host_id: 1000003, display_name: '192.168.10.13' },
        ],
        link_tpl: '/performance/detail/{bk_host_id}',
      },
      service_instances: {
        count: 2,
        instance_list: [
          { bk_service_instance_id: 2000001, display_name: '192.168.10.13_es-mock_datanode_9200' },
          { bk_service_instance_id: 2000002, display_name: '192.168.10.11_nginx_80' },
        ],
        link_tpl: null,
      },
    };
  }

  // 场景 1：K8S 多集群场景（cluster）
  if (scenario === 1) {
    return {
      cluster: {
        count: 3,
        instance_list: [
          { bcs_cluster_id: 'BCS-K8S-80001', display_name: 'MOCK-SZ-TEST-80001-INNER(BCS-K8S-80001)' },
          { bcs_cluster_id: 'BCS-K8S-80002', display_name: '模拟集群-业务测试-V1.26.1(BCS-K8S-80002)' },
          { bcs_cluster_id: 'BCS-K8S-80003', display_name: 'demo-test-gz-0611(BCS-K8S-80003)' },
        ],
        link_tpl: '/k8s?filter-bcs_cluster_id={bcs_cluster_id}&sceneId=kubernetes&sceneType=overview',
      },
    };
  }

  // 场景 2：K8S 单集群场景（node + pod + service）
  if (scenario === 2) {
    return {
      node: {
        count: 2,
        instance_list: [
          { bcs_cluster_id: 'BCS-K8S-80001', node: '192.168.10.11', display_name: 'BCS-K8S-80001/192.168.10.11' },
          { bcs_cluster_id: 'BCS-K8S-80001', node: '192.168.10.12', display_name: 'BCS-K8S-80001/192.168.10.12' },
        ],
        link_tpl:
          '/k8s?filter-bcs_cluster_id={bcs_cluster_id}&filter-node_name={node}&dashboardId=node&sceneId=kubernetes&sceneType=detail',
      },
      pod: {
        count: 3,
        instance_list: [
          {
            bcs_cluster_id: 'BCS-K8S-80001',
            pod: 'mock-prom-exporter-x7k9m',
            display_name: 'BCS-K8S-80001/mock-prom-exporter-x7k9m',
          },
          {
            bcs_cluster_id: 'BCS-K8S-80001',
            pod: 'mock-state-metrics-d4f2n',
            display_name: 'BCS-K8S-80001/mock-state-metrics-d4f2n',
          },
        ],
        link_tpl:
          '/k8s?filter-bcs_cluster_id={bcs_cluster_id}&filter-pod_name={pod}&dashboardId=pod&sceneId=kubernetes&sceneType=detail',
      },
      service: {
        count: 1,
        instance_list: [
          {
            bcs_cluster_id: 'BCS-K8S-80001',
            service: 'mock-operator-stack-state-metrics',
            display_name: 'BCS-K8S-80001/mock-operator-stack-state-metrics',
          },
        ],
        link_tpl:
          '/k8s?filter-bcs_cluster_id={bcs_cluster_id}&filter-service_name={service}&dashboardId=service&sceneId=kubernetes&sceneType=detail',
      },
    };
  }

  // 场景 3：APM 单应用场景（apm_service）
  return {
    [ImpactScopeResourceKeyEnum.APM_SERVICE]: {
      count: 2,
      instance_list: [
        {
          app_name: 'demo-app',
          service_name: 'demo-app.pushsvr',
          bk_biz_id: 9000001,
          display_name: 'demo-app/demo-app.pushsvr',
        },
        {
          app_name: 'demo-app',
          service_name: 'demo-app.gateway',
          bk_biz_id: 9000001,
          display_name: 'demo-app/demo-app.gateway',
        },
      ],
      link_tpl: '?bizId={bk_biz_id}#/apm/service?filter-app_name={app_name}&filter-service_name={service_name}',
    },
  };
};

/** mock 数据缓存，避免每次请求重新生成导致数据不稳定 */
let mockDataCache: IssueItem[] | null = null;

/**
 * @description 生成模拟 Issues 数据
 * @param {number} count - 生成数量
 * @returns {IssueItem[]} IssueItem 数组
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
    const impactScope = generateMockImpactScope(index);

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
      bk_biz_id: 100,
      bk_biz_name: '示例业务',
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
      impact_scope: impactScope,
      aggregate_config: {
        aggregate_dimensions: ['bk_target_ip'],
        conditions: [],
        alert_levels: [1, 2],
      },
    };
  });
};

/**
 * @description 模拟请求 Issues 列表接口，支持分页与排序（含网络延迟模拟）
 * @param {MockFetchParams} params - 请求参数（page / page_size / ordering）
 * @returns {Promise<{ total: number; data: IssueItem[] }>} 分页后的响应结构
 */
export const fetchMockIssues = async (
  params: Partial<MockFetchParams>,
  config: RequestOptions
): Promise<{ issues: IssueItem[]; total: number }> => {
  config;
  // 懒初始化 mock 数据缓存
  if (!mockDataCache) {
    mockDataCache = generateMockIssues(128);
  }

  const list = [...mockDataCache];

  // 排序
  const ordering = params.ordering?.[0];
  if (ordering) {
    const desc = ordering.startsWith('-');
    const field = desc ? ordering.slice(1) : ordering;
    list.sort((a, b) => {
      const va = (a as Record<string, unknown>)[field];
      const vb = (b as Record<string, unknown>)[field];
      if (typeof va === 'number' && typeof vb === 'number') {
        return desc ? vb - va : va - vb;
      }
      return desc ? String(vb).localeCompare(String(va)) : String(va).localeCompare(String(vb));
    });
  }

  // 分页
  const pageVal = params.page ?? 1;
  const pageSizeVal = params.page_size ?? 50;
  const start = (pageVal - 1) * pageSizeVal;
  const paged = list.slice(start, start + pageSizeVal);

  // 模拟网络延迟
  await new Promise(resolve => setTimeout(resolve, 300));

  return { total: list.length, issues: paged };
};

/** 状态流转映射：指派后待审核 → 未解决 */
const STATUS_AFTER_ASSIGN: Partial<Record<IssueStatusType, { status: IssueStatusType; status_display: string }>> = {
  [IssueStatusEnum.PENDING_REVIEW]: { status: IssueStatusEnum.UNRESOLVED, status_display: '未解决' },
};

/**
 * @description 模拟指派负责人接口，更新 mock 数据缓存中的 Issue 数据并返回操作结果
 * @param {AssignIssuesParams} params - 指派请求参数（issues / assignee）
 * @param {RequestOptions} config - 请求配置选项
 * @returns {Promise<IssuesOperationDialogEvent<'assign'>>} 包含 succeeded 和 failed 的操作结果
 */
export const mockAssignIssues = async (
  params: AssignIssuesParams,
  config?: RequestOptions
): Promise<IssuesOperationDialogEvent<'assign'>> => {
  config;
  // 确保 mock 数据缓存已初始化
  if (!mockDataCache) {
    mockDataCache = generateMockIssues(128);
  }

  const now = Math.floor(Date.now() / 1000);
  const succeeded: IssuesAssigneeDialogEvent[] = [];
  const failed: { issue_id: string; message: string }[] = [];

  for (const { issue_id: issueId } of params.issues) {
    // 模拟随机失败（约 5% 概率）
    if (Math.random() < 0.05) {
      failed.push({ issue_id: issueId, message: '服务端繁忙，请稍后重试' });
      continue;
    }

    const issue = mockDataCache.find(item => item.id === issueId);
    if (!issue) {
      failed.push({ issue_id: issueId, message: `Issue ${issueId} 不存在` });
      continue;
    }

    // 更新缓存中的 Issue 数据
    issue.assignee = [...params.assignee];
    issue.update_time = now;

    // 状态流转：待审核状态指派后自动变为未解决
    const transition = STATUS_AFTER_ASSIGN[issue.status];
    if (transition) {
      issue.status = transition.status;
      issue.status_display = transition.status_display;
    }

    succeeded.push({
      issue_id: issue.id,
      assignee: issue.assignee,
      status: issue.status,
      update_time: issue.update_time,
    });
  }

  // 模拟网络延迟
  await new Promise(resolve => setTimeout(resolve, 400));

  return { succeeded, failed };
};

/**
 * @description 模拟修改优先级接口，更新 mock 数据缓存中的 Issue 优先级并返回操作结果
 * @param {UpdatePriorityParams} params - 修改优先级请求参数（issues / priority）
 * @param {RequestOptions} config - 请求配置选项
 * @returns {Promise<IssuesOperationDialogEvent<'priority'>>} 包含 succeeded 和 failed 的操作结果
 */
export const mockUpdatePriority = async (
  params: UpdatePriorityParams,
  config?: RequestOptions
): Promise<IssuesOperationDialogEvent<'priority'>> => {
  config;
  // 确保 mock 数据缓存已初始化
  if (!mockDataCache) {
    mockDataCache = generateMockIssues(128);
  }

  const now = Math.floor(Date.now() / 1000);
  const succeeded: IssuesPriorityDialogEvent[] = [];
  const failed: { issue_id: string; message: string }[] = [];

  for (const { issue_id: issueId } of params.issues) {
    // 模拟随机失败（约 5% 概率）
    if (Math.random() < 0.05) {
      failed.push({ issue_id: issueId, message: '服务端繁忙，请稍后重试' });
      continue;
    }

    const issue = mockDataCache.find(item => item.id === issueId);
    if (!issue) {
      failed.push({ issue_id: issueId, message: `Issue ${issueId} 不存在` });
      continue;
    }

    // 更新缓存中的 Issue 优先级
    issue.priority = params.priority;
    issue.priority_display = { P0: '高', P1: '中', P2: '低' }[params.priority];
    issue.update_time = now;

    succeeded.push({
      issue_id: issue.id,
      priority: issue.priority,
      update_time: issue.update_time,
    });
  }

  // 模拟网络延迟
  await new Promise(resolve => setTimeout(resolve, 400));

  return { succeeded, failed };
};

/**
 * @description 模拟标记已解决接口，更新 mock 数据缓存中的 Issue 数据并返回操作结果
 * @param {ResolveIssuesParams} params - 标记已解决请求参数（issues）
 * @param {RequestOptions} config - 请求配置选项
 * @returns {Promise<IssuesOperationDialogEvent<'resolve'>>} 包含 succeeded 和 failed 的操作结果
 */
export const mockResolveIssues = async (
  params: ResolveIssuesParams,
  config?: RequestOptions
): Promise<IssuesOperationDialogEvent<'resolve'>> => {
  config;
  // 确保 mock 数据缓存已初始化
  if (!mockDataCache) {
    mockDataCache = generateMockIssues(128);
  }

  const now = Math.floor(Date.now() / 1000);
  const succeeded: IssuesResolveDialogEvent[] = [];
  const failed: { issue_id: string; message: string }[] = [];

  for (const { issue_id: issueId } of params.issues) {
    // 模拟随机失败（约 5% 概率）
    if (Math.random() < 0.05) {
      failed.push({ issue_id: issueId, message: '服务端繁忙，请稍后重试' });
      continue;
    }

    const issue = mockDataCache.find(item => item.id === issueId);
    if (!issue) {
      failed.push({ issue_id: issueId, message: `Issue ${issueId} 不存在` });
      continue;
    }

    // 更新缓存中的 Issue 数据
    issue.status = IssueStatusEnum.RESOLVED;
    issue.status_display = '已解决';
    issue.resolved_time = now;
    issue.is_resolved = true;
    issue.update_time = now;

    succeeded.push({
      issue_id: issue.id,
      resolved_time: issue.resolved_time,
      status: issue.status,
      update_time: issue.update_time,
    });
  }

  // 模拟网络延迟
  await new Promise(resolve => setTimeout(resolve, 400));

  return { succeeded, failed };
};
