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

import type {
  MetricTier,
  RumApplicationAsyncItem,
  RumAppMetricView,
  RumAppRow,
  RumAsyncMetricKey,
  RumTableItem,
} from './typings';

export type MetricMap = Partial<Record<RumAsyncMetricKey, RumApplicationAsyncItem[]>>;

/** 时间单位 → 毫秒换算系数 */
const UNIT_TO_MS: Record<string, number> = {
  ns: 0.000001,
  μs: 0.001,
  us: 0.001,
  ms: 1,
  s: 1000,
  m: 60000,
  h: 3600000,
  d: 86400000,
};

const EMPTY_METRIC: RumAppMetricView = {
  display: '--',
  tier: 'empty',
  value: null,
};

const getMetricItem = (metrics: MetricMap, key: RumAsyncMetricKey, applicationId: number) =>
  metrics[key]?.find(item => `${item.application_id}` === `${applicationId}`)?.[key];

const getLcpTier = (value: number): MetricTier => {
  if (value <= 2500) return 'good';
  if (value <= 4000) return 'warn';
  return 'bad';
};

const getRateTier = (value: number, warnValue: number, badValue: number): MetricTier => {
  if (value <= warnValue) return 'good';
  if (value <= badValue) return 'warn';
  return 'bad';
};

/**
 * 构建指标视图，时间单位自动转换为 ms 基准值用于排序/比较
 */
const buildMetricView = (
  value: null | number | undefined,
  unit: string,
  getTier: (value: number) => MetricTier
): RumAppMetricView => {
  if (value == null || Number.isNaN(value)) return EMPTY_METRIC;
  /** 时间单位需转为 ms 基准值，非时间单位（如 %）直接使用原始值 */
  const normalizedValue = unit in UNIT_TO_MS ? value * UNIT_TO_MS[unit] : value;
  return {
    value: normalizedValue,
    tier: getTier(normalizedValue),
    display: `${value}${unit}`,
  };
};

const getDataStatusText = (dataStatus: RumTableItem['data_status']) => {
  const textMap = {
    normal: window.i18n.t('正常'),
    no_data: window.i18n.t('无数据'),
    disabled: window.i18n.t('已禁用'),
  };
  return textMap[dataStatus] || '--';
};

export const buildRumAppRows = (applications: RumTableItem[], metrics: MetricMap): RumAppRow[] =>
  applications.map(app => {
    const lcpMetric = getMetricItem(metrics, 'lcp_p75', app.application_id);
    const jsErrorMetric = getMetricItem(metrics, 'js_error_rate', app.application_id);
    const apiFailMetric = getMetricItem(metrics, 'api_fail_rate', app.application_id);

    return {
      id: String(app.application_id),
      applicationId: app.application_id,
      bkBizId: app.bk_biz_id,
      appName: app.app_name,
      appAlias: app.app_alias,
      description: app.description,
      clientType: app.client_type,
      isEnabled: app.is_enabled,
      appStatus: app.is_enabled ? window.i18n.t('启用') : window.i18n.t('停用'),
      dataStatus: app.data_status,
      dataStatusText: getDataStatusText(app.data_status),
      spanResultTableId: app.span_result_table_id,
      metricResultTableId: app.metric_result_table_id,
      isCreateFinished: app.is_create_finished,
      permission: app.permission,
      lcpP75: buildMetricView(lcpMetric?.value, lcpMetric?.unit || 'ms', getLcpTier),
      jsErrorRate: buildMetricView(jsErrorMetric?.value, jsErrorMetric?.unit || '%', value =>
        getRateTier(value, 0.5, 2)
      ),
      apiFailRate: buildMetricView(apiFailMetric?.value, apiFailMetric?.unit || '%', value => getRateTier(value, 1, 3)),
    };
  });
