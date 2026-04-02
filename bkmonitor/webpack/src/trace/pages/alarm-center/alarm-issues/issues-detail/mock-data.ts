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

import { IssuePriorityEnum, IssueStatusEnum, TrendStatusEnum } from '../constant';

import type { DimensionSummaryItem, IssueDetail, IssueDetailParams, IssueTrendItem } from '../typing';

/* ============== 模拟数据常量 ============== */

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

/** 模拟策略列表 */
const MOCK_STRATEGIES = [
  { id: '1001', name: '主机 CPU 使用率过高' },
  { id: '1002', name: '服务响应超时' },
  { id: '1003', name: '数据库连接异常' },
  { id: '1004', name: 'Pod 重启频繁' },
];

/** 模拟标签组合列表 */
const MOCK_LABEL_GROUPS = [
  ['集群告警', '测试环境', 'BCS'],
  ['集群告警', '生产环境'],
  ['单机告警', 'BCS'],
  ['服务告警', '测试环境', 'K8S'],
  ['网络告警', '生产环境', 'BCS'],
];

/** 业务列表 */
const MOCK_BUSINESSES = [
  { id: 100, name: '蓝鲸' },
  { id: 200, name: '示例业务' },
  { id: 300, name: '测试业务' },
];

/* ============== 工具函数 ============== */

/** 随机选择数组元素 */
const randomPick = <T>(arr: T[]): T => arr[Math.floor(Math.random() * arr.length)];

/** 生成随机 ID */
const generateId = () => `${Date.now()}${Math.random().toString(36).slice(2, 11)}`;

/** 生成随机时间戳（秒级，最近 30 天内） */
const randomTimestamp = (daysAgo = 30): number => {
  const now = Math.floor(Date.now() / 1000);
  const offset = Math.floor(Math.random() * daysAgo * 24 * 60 * 60);
  return now - offset;
};

/** 计算存活时长 */
const calculateDuration = (startTime: number, endTime: number): string => {
  const diffSeconds = endTime - startTime;
  const days = Math.floor(diffSeconds / 86400);
  const hours = Math.floor((diffSeconds % 86400) / 3600);
  const minutes = Math.floor((diffSeconds % 3600) / 60);

  if (days > 0) {
    return hours > 0 ? `${days}d ${hours}h` : `${days}d`;
  }
  if (hours > 0) {
    return minutes > 0 ? `${hours}h ${minutes}min` : `${hours}h`;
  }
  return `${minutes}min`;
};

/** 生成趋势数据 */
const generateTrendData = (startTimestamp: number, endTimestamp: number): IssueTrendItem[] => {
  const dayMs = 24 * 60 * 60 * 1000;
  const dataPoints: [number, number][] = [];

  // 按天生成数据点
  for (let ts = startTimestamp * 1000; ts <= endTimestamp * 1000; ts += dayMs) {
    dataPoints.push([ts, Math.floor(Math.random() * 10) + 1]);
  }

  return [
    {
      name: TrendStatusEnum.ABNORMAL,
      display_name: '未恢复',
      data: dataPoints.map(([ts]) => [ts, Math.floor(Math.random() * 5) + 1]),
    },
    {
      name: TrendStatusEnum.RECOVERED,
      display_name: '已恢复',
      data: dataPoints.map(([ts]) => [ts, Math.floor(Math.random() * 3)]),
    },
    {
      name: TrendStatusEnum.CLOSED,
      display_name: '已失效',
      data: dataPoints.map(([ts]) => [ts, Math.floor(Math.random() * 2)]),
    },
  ];
};

/** 生成维度统计数据 */
const generateDimensionSummary = (): DimensionSummaryItem[] => {
  const dimensions = [
    { key: 'bk_target_ip', name: '主机IP' },
    { key: 'bk_target_cloud_id', name: '云区域' },
    { key: 'bcs_cluster_id', name: '集群' },
  ];

  return dimensions.map(({ key, name }) => {
    const totalCount = Math.floor(Math.random() * 100) + 50;
    const items: DimensionSummaryItem['items'] = [];

    let remainingCount = totalCount;
    const values = ['10.0.0.1', '10.0.0.2', '10.0.0.3', '10.0.0.4', '10.0.0.5'];

    values.forEach((value, index) => {
      const count = index === values.length - 1 ? remainingCount : Math.floor(remainingCount * 0.3);
      remainingCount -= count;
      items.push({
        value,
        count,
        percentage: Math.round((count / totalCount) * 10000) / 100,
      });
    });

    // 添加"其他"
    if (remainingCount > 0) {
      items.push({
        value: '其他',
        count: remainingCount,
        percentage: Math.round((remainingCount / totalCount) * 10000) / 100,
      });
    }

    return {
      dimension_key: key,
      dimension_name: name,
      total_count: totalCount,
      items,
    };
  });
};

/** 生成影响范围 */
const generateImpactScope = (): IssueDetail['impact_scope'] => {
  const clusterCount = Math.floor(Math.random() * 5) + 1;
  return {
    cluster: {
      display_name: '集群',
      count: clusterCount,
      instance_list: Array.from({ length: Math.min(clusterCount, 3) }, (_, i) => ({
        bcs_cluster_id: `BCS-K8S-${80001 + i}`,
        display_name: `MOCK-CLUSTER-${80001 + i}(BCS-K8S-${80001 + i})`,
      })),
      link_tpl: '/k8s?filter-bcs_cluster_id={bcs_cluster_id}&sceneId=kubernetes&sceneType=overview',
    },
    host: {
      display_name: '主机',
      count: Math.floor(Math.random() * 20) + 5,
      instance_list: Array.from({ length: 3 }, (_, i) => ({
        bk_host_id: 1000 + i,
        display_name: `192.168.1.${10 + i}`,
      })),
      link_tpl: '/host?filter-bk_host_id={bk_host_id}',
    },
  };
};

/* ============== 导出 Mock 数据 ============== */

/** 生成 Issue 详情 Mock 数据 */
export const generateIssueDetailMock = (id?: string): IssueDetail => {
  const strategy = randomPick(MOCK_STRATEGIES);
  const business = randomPick(MOCK_BUSINESSES);
  const status = randomPick([IssueStatusEnum.UNRESOLVED, IssueStatusEnum.RESOLVED, IssueStatusEnum.PENDING_REVIEW]);
  const priority = randomPick([IssuePriorityEnum.P0, IssuePriorityEnum.P1, IssuePriorityEnum.P2]);
  const firstAlertTime = randomTimestamp(30);
  const lastAlertTime = randomTimestamp(7); // 最近 7 天
  const createTime = firstAlertTime - Math.floor(Math.random() * 100);
  const updateTime = lastAlertTime + Math.floor(Math.random() * 3600);
  const isResolved = status === IssueStatusEnum.RESOLVED;

  const alertCount = Math.floor(Math.random() * 200) + 10;
  const alertIds = Array.from({ length: alertCount }, (_, i) => `alert-${generateId()}-${i}`);

  return {
    id: id ?? generateId(),
    name: strategy.name,
    anomaly_message: randomPick(MOCK_ANOMALY_MESSAGES),
    status,
    status_display:
      status === IssueStatusEnum.UNRESOLVED
        ? '未解决'
        : status === IssueStatusEnum.RESOLVED
          ? '已解决'
          : status === IssueStatusEnum.PENDING_REVIEW
            ? '待审核'
            : '归档',
    is_regression: Math.random() > 0.5,
    priority,
    priority_display: priority === IssuePriorityEnum.P0 ? '高' : priority === IssuePriorityEnum.P1 ? '中' : '低',
    assignee: Math.random() > 0.2 ? [randomPick(MOCK_USERS)] : [],
    strategy_id: strategy.id,
    strategy_name: strategy.name,
    bk_biz_id: business.id,
    bk_biz_name: business.name,
    labels: randomPick(MOCK_LABEL_GROUPS),
    alert_count: alertCount,
    alert_ids: alertIds,
    earliest_alert_id: alertIds[0],
    latest_alert_id: alertIds[alertIds.length - 1],
    first_alert_time: firstAlertTime,
    last_alert_time: lastAlertTime,
    create_time: createTime,
    update_time: updateTime,
    resolved_time: isResolved ? updateTime : null,
    is_resolved: isResolved,
    duration: calculateDuration(firstAlertTime, updateTime),
    impact_scope: generateImpactScope(),
    aggregate_config: {
      aggregate_dimensions: ['bk_target_ip'],
      conditions: [],
      alert_levels: [1, 2],
    },
    dimension_summary: generateDimensionSummary(),
    trend: generateTrendData(firstAlertTime, lastAlertTime),
  };
};

/** 默认 Issue 详情 Mock 数据 */
export const DEFAULT_ISSUE_DETAIL_MOCK: IssueDetail = generateIssueDetailMock('mock-issue-001');

/* ============== 模拟异步请求 ============== */

/** 模拟网络延迟 */
const delay = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));

/** 模拟请求延迟范围（毫秒） */
const MOCK_DELAY_RANGE = {
  min: 200,
  max: 800,
};

/** 获取随机延迟时间 */
const getRandomDelay = () =>
  Math.floor(Math.random() * (MOCK_DELAY_RANGE.max - MOCK_DELAY_RANGE.min)) + MOCK_DELAY_RANGE.min;

/**
 * 异步获取 Issue 详情 Mock 数据
 * @param id Issue ID，不传则随机生成
 * @param delayMs 延迟时间（毫秒），不传则随机 200-800ms
 */
export const fetchIssueDetailMock = async (params: IssueDetailParams, delayMs?: number): Promise<IssueDetail> => {
  const actualDelay = delayMs ?? getRandomDelay();
  await delay(actualDelay);
  console.log('[Mock] fetchIssueDetailMock for issue: ', params);
  return generateIssueDetailMock(params.id);
};
