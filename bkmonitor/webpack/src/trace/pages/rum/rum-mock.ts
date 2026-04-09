/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition):
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

/** 指标展示档位：绿 / 黄 / 红 / 无数据 */
export type MetricTier = 'bad' | 'empty' | 'good' | 'warn';

export interface RumAppRow {
  accessStatus: string;
  alias: string;
  apiFailDisplay: string;
  apiFailTier: MetricTier;
  appStatus: string;
  dataStatus: 'ok' | 'warn';
  domain: string;
  id: string;
  jsErrorDisplay: string;
  jsErrorTier: MetricTier;
  lcpDisplay: string;
  lcpTier: MetricTier;
}

type RumAppRowCore = Omit<RumAppRow, 'accessStatus' | 'appStatus'>;

/**
 * Mock：覆盖指标绿/黄/红/无数据、数据状态正常/异常、长文案与短文案等，便于联调前验 UI。
 * 档位与样式：good→绿、warn→橙、bad→红、empty→「--」灰。
 * accessStatus / appStatus 由末尾映射生成，与列表搜索、表头筛选联动演示一致。
 */
const MOCK_TABLE_DATA_CORE: RumAppRowCore[] = [
  // 基线：三指标均有值，整体健康，API 略高但仍为黄档
  {
    id: '1',
    domain: 'www.example.com',
    alias: 'Web 端官网',
    lcpTier: 'good',
    lcpDisplay: '1.8s',
    jsErrorTier: 'good',
    jsErrorDisplay: '0.2%',
    apiFailTier: 'warn',
    apiFailDisplay: '1.5%',
    dataStatus: 'ok',
  },
  // LCP 红档，其余绿
  {
    id: '2',
    domain: 'slow-shop.demo.com',
    alias: '电商大促活动页',
    lcpTier: 'bad',
    lcpDisplay: '5.2s',
    jsErrorTier: 'good',
    jsErrorDisplay: '0.1%',
    apiFailTier: 'good',
    apiFailDisplay: '0.4%',
    dataStatus: 'ok',
  },
  // JS 错误率红档
  {
    id: '3',
    domain: 'legacy-app.internal.woa.com',
    alias: '遗留脚本较多业务',
    lcpTier: 'good',
    lcpDisplay: '1.9s',
    jsErrorTier: 'bad',
    jsErrorDisplay: '4.8%',
    apiFailTier: 'good',
    apiFailDisplay: '0.6%',
    dataStatus: 'ok',
  },
  // API 失败率红档
  {
    id: '4',
    domain: 'api-heavy.saas.com',
    alias: '重 API 控制台',
    lcpTier: 'good',
    lcpDisplay: '2.0s',
    jsErrorTier: 'good',
    jsErrorDisplay: '0.3%',
    apiFailTier: 'bad',
    apiFailDisplay: '9.6%',
    dataStatus: 'ok',
  },
  // 三指标均为黄档（临界体验）
  {
    id: '5',
    domain: 'mid-tier.app.com',
    alias: '综合偏高',
    lcpTier: 'warn',
    lcpDisplay: '2.9s',
    jsErrorTier: 'warn',
    jsErrorDisplay: '1.4%',
    apiFailTier: 'warn',
    apiFailDisplay: '2.8%',
    dataStatus: 'ok',
  },
  // LCP 黄、JS 红、API 绿（交叉）
  {
    id: '6',
    domain: 'render-heavy.io',
    alias: '首屏渲染重',
    lcpTier: 'warn',
    lcpDisplay: '3.1s',
    jsErrorTier: 'bad',
    jsErrorDisplay: '3.2%',
    apiFailTier: 'good',
    apiFailDisplay: '0.5%',
    dataStatus: 'ok',
  },
  // LCP 绿、JS 黄、API 红
  {
    id: '7',
    domain: 'gateway-timeout.bk.com',
    alias: '网关抖动期',
    lcpTier: 'good',
    lcpDisplay: '1.4s',
    jsErrorTier: 'warn',
    jsErrorDisplay: '1.1%',
    apiFailTier: 'bad',
    apiFailDisplay: '7.3%',
    dataStatus: 'ok',
  },
  // 仅 LCP 无数据，其余正常（部分上报场景）
  {
    id: '8',
    domain: 'partial-rum.example.com',
    alias: '部分探针未就绪',
    lcpTier: 'empty',
    lcpDisplay: '--',
    jsErrorTier: 'good',
    jsErrorDisplay: '0.2%',
    apiFailTier: 'good',
    apiFailDisplay: '0.3%',
    dataStatus: 'ok',
  },
  // 仅 JS 无数据
  {
    id: '9',
    domain: 'js-sdk-missing.corp.net',
    alias: 'JS SDK 未注入',
    lcpTier: 'good',
    lcpDisplay: '1.7s',
    jsErrorTier: 'empty',
    jsErrorDisplay: '--',
    apiFailTier: 'warn',
    apiFailDisplay: '2.1%',
    dataStatus: 'ok',
  },
  // 仅 API 无数据
  {
    id: '10',
    domain: 'static-only.site.org',
    alias: '纯静态站点',
    lcpTier: 'good',
    lcpDisplay: '1.1s',
    jsErrorTier: 'good',
    jsErrorDisplay: '0.0%',
    apiFailTier: 'empty',
    apiFailDisplay: '--',
    dataStatus: 'ok',
  },
  // 长域名 + 长别名（省略号）
  {
    id: '11',
    domain: 'very-long-subdomain-name-for-ellipsis-test.bkapps.example.woa.com',
    alias: '蓝鲸某业务线前端监控示例应用别名超长展示',
    lcpTier: 'good',
    lcpDisplay: '1.6s',
    jsErrorTier: 'good',
    jsErrorDisplay: '0.4%',
    apiFailTier: 'good',
    apiFailDisplay: '0.2%',
    dataStatus: 'ok',
  },
  // 短域名短别名
  {
    id: '12',
    domain: 'x.cn',
    alias: '短',
    lcpTier: 'warn',
    lcpDisplay: '2.4s',
    jsErrorTier: 'warn',
    jsErrorDisplay: '0.9%',
    apiFailTier: 'warn',
    apiFailDisplay: '1.9%',
    dataStatus: 'ok',
  },
  // 全指标无数据 + 数据状态异常（接入/采集中断）
  {
    id: '13',
    domain: 'bklog.woa.com',
    alias: '日志平台',
    lcpTier: 'empty',
    lcpDisplay: '--',
    jsErrorTier: 'empty',
    jsErrorDisplay: '--',
    apiFailTier: 'empty',
    apiFailDisplay: '--',
    dataStatus: 'warn',
  },
  {
    id: '14',
    domain: 'offline-app.local',
    alias: '已下线保留配置',
    lcpTier: 'empty',
    lcpDisplay: '--',
    jsErrorTier: 'empty',
    jsErrorDisplay: '--',
    apiFailTier: 'empty',
    apiFailDisplay: '--',
    dataStatus: 'warn',
  },
  // 数据状态异常但历史行曾有个别残留值（边界）
  {
    id: '15',
    domain: 'stale-metrics.demo.com',
    alias: '采集中断残留',
    lcpTier: 'empty',
    lcpDisplay: '--',
    jsErrorTier: 'empty',
    jsErrorDisplay: '--',
    apiFailTier: 'warn',
    apiFailDisplay: '1.2%',
    dataStatus: 'warn',
  },
  // 全绿极值（最优）
  {
    id: '16',
    domain: 'perf-best.cdn.com',
    alias: 'CDN 加速落地页',
    lcpTier: 'good',
    lcpDisplay: '0.9s',
    jsErrorTier: 'good',
    jsErrorDisplay: '0.0%',
    apiFailTier: 'good',
    apiFailDisplay: '0.0%',
    dataStatus: 'ok',
  },
  // 全红（极差）
  {
    id: '17',
    domain: 'chaos-test.env',
    alias: '故障注入压测',
    lcpTier: 'bad',
    lcpDisplay: '6.8s',
    jsErrorTier: 'bad',
    jsErrorDisplay: '6.2%',
    apiFailTier: 'bad',
    apiFailDisplay: '11.4%',
    dataStatus: 'ok',
  },
  {
    id: '18',
    domain: 'bkvision.woa.com',
    alias: 'bkvision',
    lcpTier: 'empty',
    lcpDisplay: '--',
    jsErrorTier: 'empty',
    jsErrorDisplay: '--',
    apiFailTier: 'empty',
    apiFailDisplay: '--',
    dataStatus: 'warn',
  },
];

export const MOCK_TABLE_DATA: RumAppRow[] = MOCK_TABLE_DATA_CORE.map((row, i) => ({
  ...row,
  accessStatus: i % 3 === 0 ? '未接入' : '已接入',
  appStatus: i % 2 === 0 ? '启用' : '停用',
}));
