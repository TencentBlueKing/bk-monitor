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

export type MetricTier = 'bad' | 'empty' | 'good' | 'warn';

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

export type RumApiColumnType = 'link' | 'number' | 'string';

export interface RumApplication {
  app_alias: string;
  app_name: string;
  application_id: number;
  bk_biz_id: number;
  client_type: string;
  data_status: 'no_data' | 'normal';
  description: string;
  is_create_finished: boolean;
  is_enabled: boolean;
  metric_result_table_id: string;
  permission: Record<string, boolean>;
  span_data_status?: string;
  span_result_table_id: string;
}

export type RumApplicationAsyncItem = Partial<Record<RumAsyncMetricKey, RumAsyncMetricValue>> & {
  app_name: string;
  application_id: number;
};

export interface RumApplicationListResponse {
  columns: RumApiColumn[];
  data: RumApplication[];
  total: number;
}

export interface RumAppMetricView {
  display: string;
  tier: MetricTier;
  value: null | number;
}

export interface RumAppRow {
  apiFailRate: RumAppMetricView;
  appAlias: string;
  applicationId: number;
  appName: string;
  appStatus: string;
  bkBizId: number;
  clientType: string;
  dataStatus: RumApplication['data_status'];
  dataStatusText: string;
  description: string;
  id: string;
  isCreateFinished: boolean;
  isEnabled: boolean;
  jsErrorRate: RumAppMetricView;
  lcpP75: RumAppMetricView;
  metricResultTableId: string;
  permission: Record<string, boolean>;
  spanResultTableId: string;
}

export type RumAsyncMetricKey = 'api_fail_rate' | 'js_error_rate' | 'lcp_p75';

export interface RumAsyncMetricValue {
  id: RumAsyncMetricKey;
  name: string;
  unit: '%' | 'ms';
  value: number;
}

export const MOCK_APPLICATION_LIST_RESPONSE: RumApplicationListResponse = {
  columns: [
    {
      id: 'app_name',
      name: '应用名称',
      disabled: true,
      checked: true,
      sortable: false,
      type: 'link',
      width: null,
      min_width: 200,
      max_width: null,
      filterable: false,
      filter_list: [],
      actionId: 'view_rum_application',
      asyncable: false,
      props: {},
      showOverflowTooltip: true,
    },
    {
      id: 'app_alias',
      name: '展示名称',
      disabled: false,
      checked: true,
      sortable: false,
      type: 'string',
      width: null,
      min_width: 120,
      max_width: null,
      filterable: false,
      filter_list: [],
      actionId: null,
      asyncable: false,
      props: {},
      showOverflowTooltip: true,
    },
    {
      id: 'description',
      name: '描述',
      disabled: false,
      checked: true,
      sortable: false,
      type: 'string',
      width: null,
      min_width: 160,
      max_width: null,
      filterable: false,
      filter_list: [],
      actionId: null,
      asyncable: false,
      props: {},
      showOverflowTooltip: true,
    },
  ],
  total: 6,
  data: [
    {
      application_id: 101,
      bk_biz_id: 2,
      app_name: 'www-example-com',
      app_alias: '示例官网',
      description: '示例官网前端监控',
      client_type: 'web',
      is_enabled: true,
      data_status: 'normal',
      span_result_table_id: '2_bkrum_span_www_example_com',
      metric_result_table_id: '2_bkrum_metric_www_example_com.__default__',
      is_create_finished: true,
      permission: {
        manage_rum_application: true,
        view_rum_application: true,
      },
    },
    {
      application_id: 102,
      bk_biz_id: 2,
      app_name: 'bk-console',
      app_alias: '蓝鲸管理台',
      description: '蓝鲸管理台前端性能监控',
      client_type: 'web',
      is_enabled: true,
      span_data_status: 'normal',
      data_status: 'no_data',
      span_result_table_id: '2_bkrum_span_bk_console',
      metric_result_table_id: '2_bkrum_metric_bk_console.__default__',
      is_create_finished: true,
      permission: {
        manage_rum_application: true,
        view_rum_application: true,
      },
    },
    {
      application_id: 103,
      bk_biz_id: 2,
      app_name: 'bk-monitor-web',
      app_alias: '监控平台',
      description: '监控平台用户端体验监控',
      client_type: 'web',
      is_enabled: true,
      data_status: 'normal',
      span_result_table_id: '2_bkrum_span_bk_monitor_web',
      metric_result_table_id: '2_bkrum_metric_bk_monitor_web.__default__',
      is_create_finished: true,
      permission: {
        manage_rum_application: true,
        view_rum_application: true,
      },
    },
    {
      application_id: 104,
      bk_biz_id: 2,
      app_name: 'event-promotion',
      app_alias: '活动专题页',
      description: '大促活动落地页前端监控',
      client_type: 'web',
      is_enabled: false,
      data_status: 'no_data',
      span_result_table_id: '2_bkrum_span_event_promotion',
      metric_result_table_id: '2_bkrum_metric_event_promotion.__default__',
      is_create_finished: true,
      permission: {
        manage_rum_application: false,
        view_rum_application: true,
      },
    },
    {
      application_id: 105,
      bk_biz_id: 2,
      app_name: 'api-heavy-console',
      app_alias: '重 API 控制台',
      description: 'API 调用密集型控制台',
      client_type: 'web',
      is_enabled: true,
      data_status: 'normal',
      span_result_table_id: '2_bkrum_span_api_heavy_console',
      metric_result_table_id: '2_bkrum_metric_api_heavy_console.__default__',
      is_create_finished: true,
      permission: {
        manage_rum_application: true,
        view_rum_application: true,
      },
    },
    {
      application_id: 106,
      bk_biz_id: 2,
      app_name: 'static-docs',
      app_alias: '静态文档站',
      description: '无 API 请求的静态文档站点',
      client_type: 'web',
      is_enabled: true,
      data_status: 'normal',
      span_result_table_id: '2_bkrum_span_static_docs',
      metric_result_table_id: '2_bkrum_metric_static_docs.__default__',
      is_create_finished: true,
      permission: {
        manage_rum_application: true,
        view_rum_application: true,
      },
    },
  ],
};

const buildAsyncMetricItem = (
  application_id: number,
  app_name: string,
  key: RumAsyncMetricKey,
  name: string,
  value: number,
  unit: RumAsyncMetricValue['unit']
): RumApplicationAsyncItem => {
  const item: RumApplicationAsyncItem = {
    application_id,
    app_name,
  };
  item[key] = {
    id: key,
    name,
    value,
    unit,
  };
  return item;
};

export const MOCK_APPLICATION_ASYNC_RESPONSES: Record<RumAsyncMetricKey, RumApplicationAsyncItem[]> = {
  lcp_p75: [
    buildAsyncMetricItem(101, 'www-example-com', 'lcp_p75', 'LCP P75', 1850, 'ms'),
    buildAsyncMetricItem(102, 'bk-console', 'lcp_p75', 'LCP P75', 3210, 'ms'),
    buildAsyncMetricItem(103, 'bk-monitor-web', 'lcp_p75', 'LCP P75', 1420, 'ms'),
    buildAsyncMetricItem(104, 'event-promotion', 'lcp_p75', 'LCP P75', 0, 'ms'),
    buildAsyncMetricItem(105, 'api-heavy-console', 'lcp_p75', 'LCP P75', 4380, 'ms'),
    buildAsyncMetricItem(106, 'static-docs', 'lcp_p75', 'LCP P75', 960, 'ms'),
  ],
  js_error_rate: [
    buildAsyncMetricItem(101, 'www-example-com', 'js_error_rate', 'JS 错误率', 0.2, '%'),
    buildAsyncMetricItem(102, 'bk-console', 'js_error_rate', 'JS 错误率', 0, '%'),
    buildAsyncMetricItem(103, 'bk-monitor-web', 'js_error_rate', 'JS 错误率', 1.4, '%'),
    buildAsyncMetricItem(104, 'event-promotion', 'js_error_rate', 'JS 错误率', 0, '%'),
    buildAsyncMetricItem(105, 'api-heavy-console', 'js_error_rate', 'JS 错误率', 4.8, '%'),
    buildAsyncMetricItem(106, 'static-docs', 'js_error_rate', 'JS 错误率', 0.05, '%'),
  ],
  api_fail_rate: [
    buildAsyncMetricItem(101, 'www-example-com', 'api_fail_rate', 'API 失败率', 1.5, '%'),
    buildAsyncMetricItem(102, 'bk-console', 'api_fail_rate', 'API 失败率', 0, '%'),
    buildAsyncMetricItem(103, 'bk-monitor-web', 'api_fail_rate', 'API 失败率', 2.8, '%'),
    buildAsyncMetricItem(104, 'event-promotion', 'api_fail_rate', 'API 失败率', 0, '%'),
    buildAsyncMetricItem(105, 'api-heavy-console', 'api_fail_rate', 'API 失败率', 9.6, '%'),
    buildAsyncMetricItem(106, 'static-docs', 'api_fail_rate', 'API 失败率', 0, '%'),
  ],
};
