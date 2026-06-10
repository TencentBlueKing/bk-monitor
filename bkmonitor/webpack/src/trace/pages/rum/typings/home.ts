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

/** 权限信息 */
export interface IPermission {
  [actionId: string]: boolean;
}

/** 指标等级 */
export type MetricTier = 'bad' | 'empty' | 'good' | 'warn';

/** API 列定义 */
export interface RumApiColumn {
  actionId: null | string;
  asyncable: boolean;
  checked: boolean;
  disabled: boolean;
  filter_list: { label: string; value: string }[];
  filterable: boolean;
  id: string;
  max_width: null | number;
  min_width: null | number;
  name: string;
  props: Record<string, unknown>;
  showOverflowTooltip: boolean;
  sortable: 'custom' | boolean;
  type: RumApiColumnType;
  width: null | number;
}

/** API 列类型 */
export type RumApiColumnType = 'link' | 'number' | 'string';

/** 应用异步指标项 */
export type RumApplicationAsyncItem = Partial<Record<RumAsyncMetricKey, RumAsyncMetricValue>> & {
  app_name: string;
  application_id: number;
};

/** 应用列表响应 */
export interface RumApplicationListResponse {
  columns: RumApiColumn[];
  data: RumTableItem[];
  total: number;
}

/** 应用指标视图 */
export interface RumAppMetricView {
  display: string;
  tier: MetricTier;
  value: null | number;
}

/** 应用行数据（前端展示用） */
export interface RumAppRow {
  apiFailRate: RumAppMetricView;
  appAlias: string;
  applicationId: number;
  appName: string;
  appStatus: string;
  bkBizId: number;
  clientType: string;
  dataStatus: RumTableItem['data_status'];
  dataStatusText: string;
  description: string;
  id: string;
  isCreateFinished: boolean;
  isEnabled: boolean;
  jsErrorRate: RumAppMetricView;
  lcpP75: RumAppMetricView;
  metricResultTableId: string;
  permission: IPermission;
  spanResultTableId: string;
}

/** 异步指标键 */
export type RumAsyncMetricKey = 'api_fail_rate' | 'js_error_rate' | 'lcp_p75';

/** 异步指标值 */
export interface RumAsyncMetricValue {
  id: RumAsyncMetricKey;
  name: string;
  unit: '%' | 'ms';
  value: number;
}

/** RUM 应用列表项 */
export interface RumTableItem {
  /** 展示名称 */
  app_alias: string;
  /** 应用名称 */
  app_name: string;
  /** 应用 ID */
  application_id: number;
  /** 业务 ID */
  bk_biz_id: number;
  /** 前端类型 */
  client_type: string;
  /** span 数据状态镜像值 */
  data_status: 'disabled' | 'no_data' | 'normal';
  /** 描述 */
  description: string;
  /** 是否建链完成 */
  is_create_finished: boolean;
  /** 应用是否启用 */
  is_enabled: boolean;
  /** 指标结果表 */
  metric_result_table_id: string;
  /** 权限信息 */
  permission: IPermission;
  /** span 数据状态（可选） */
  span_data_status?: string;
  /** span 原始结果表 */
  span_result_table_id: string;
}

/** 排序指标字段枚举（单一数据源，类型与常量均由此推导） */
const SortableMetric = {
  lcpP75: 'lcpP75',
  jsErrorRate: 'jsErrorRate',
  apiFailRate: 'apiFailRate',
} as const;

/** 由 SortableMetric 自动推导的联合类型 */
export type SortableMetricKey = (typeof SortableMetric)[keyof typeof SortableMetric];

/** 排序字段常量数组，与 SortableMetric 联动 */
export const SORTABLE_METRIC_KEYS = Object.values(SortableMetric) as readonly SortableMetricKey[];

/** 排序列的标题 i18n key 映射 */
export const METRIC_COLUMN_TITLES: Record<SortableMetricKey, string> = {
  [SortableMetric.lcpP75]: 'LCP P75',
  [SortableMetric.jsErrorRate]: 'JS 错误率',
  [SortableMetric.apiFailRate]: 'API 失败率',
};
