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

/**
 * 分析板块里原本新开页的入口，改为在 AI 诊断会话里以回答内容回显。
 * 这里定义回答能承载的结构化结果，渲染见 chat-result-card.tsx。
 */

export const ChatResultKind = {
  /** 异常维度（组合）的指标趋势 */
  METRIC: 'metric',
  /** 维度组关联的告警列表 */
  ALERT_LIST: 'alert-list',
  /** 日志聚类明细 */
  LOG_CLUSTER: 'log-cluster',
  /** 事件列表 */
  EVENT_LIST: 'event-list',
} as const;

export type ChatResultKindType = (typeof ChatResultKind)[keyof typeof ChatResultKind];

/** 一条时序曲线，datapoints 沿用监控的 [value, timestamp] 约定 */
export interface IChatSeries {
  color: string;
  datapoints: [number, number][];
  name: string;
}

/** 指标趋势 */
export interface IChatMetricResult {
  /** 生成这条曲线用到的维度条件 */
  conditions: { name: string; value: string }[];
  kind: typeof ChatResultKind.METRIC;
  series: IChatSeries[];
  title: string;
  unit?: string;
}

export interface IChatAlertItem {
  beginTime: string;
  id: string;
  name: string;
  /** 告警级别，1 致命 / 2 预警 / 3 提醒 */
  severity: 1 | 2 | 3;
  status: string;
  strategyName: string;
}

/** 告警列表 */
export interface IChatAlertListResult {
  alerts: IChatAlertItem[];
  kind: typeof ChatResultKind.ALERT_LIST;
  /** 命中总数，可能大于 alerts.length */
  total: number;
}

/** 日志聚类明细 */
export interface IChatLogClusterResult {
  demoLogs: string[];
  kind: typeof ChatResultKind.LOG_CLUSTER;
  logCount: number;
  pattern: string;
  /** 按时间分布的出现次数 */
  trend: IChatSeries[];
}

export interface IChatEventItem {
  content: string;
  name: string;
  source: string;
  time: string;
}

/** 事件列表 */
export interface IChatEventListResult {
  events: IChatEventItem[];
  kind: typeof ChatResultKind.EVENT_LIST;
  total: number;
  unit: string;
}

export type IChatResult = IChatAlertListResult | IChatEventListResult | IChatLogClusterResult | IChatMetricResult;

/** 板块发起回显时携带的上下文，由 mock 层据此拼出结果 */
export interface IChatResultContext {
  alertCount?: number;
  /** 异常维度（组合）的维度明细 */
  dimensions?: { name: string; value: string }[];
  eventGroup?: string;
  eventTotal?: number;
  eventUnit?: string;
  logCount?: number;
  /** 日志聚类的 Pattern */
  pattern?: string;
  strategies?: { strategy_id: number; strategy_name: string }[];
}

/** 板块 → AI 诊断会话的回显请求 */
export interface IChatResultRequest {
  context?: IChatResultContext;
  kind: ChatResultKindType;
  /** 递增以强制重复触发同一请求 */
  nonce: number;
  /** 落在会话里的用户提问气泡文案 */
  question: string;
}
