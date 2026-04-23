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

import type { IStrategyData } from '../../../typings';

// ===================== 类型定义 =====================

/** 数据状态枚举值 */
type DataStatusType = 'DISABLED' | 'NO_DATA' | 'NORMAL';

/** 1.15 GetDataSamplingResource 采样数据项 */
interface IDataSamplingItem {
  /** 原始样例数据 */
  raw_log: Record<string, unknown>;
  /** 采样时间 */
  sampling_time: string;
}

/** 1.15 GetDataSamplingResource 响应 */
type IDataSamplingResponse = IDataSamplingItem[];

/** 1.14 GetDataStatusResource 响应 */
interface IDataStatusResponse {
  /** 数据状态：NORMAL-正常 / NO_DATA-无数据 / DISABLED-已停用 */
  span: DataStatusType;
}

// ===================== Mock 数据 =====================

/** 1.14 GetDataStatusResource — 数据状态（正常） */
export const MOCK_DATA_STATUS_NORMAL: IDataStatusResponse = {
  span: 'NORMAL',
};

/** 1.14 GetDataStatusResource — 数据状态（无数据） */
export const MOCK_DATA_STATUS_NO_DATA: IDataStatusResponse = {
  span: 'NO_DATA',
};

/** 1.14 GetDataStatusResource — 数据状态（已停用） */
export const MOCK_DATA_STATUS_DISABLED: IDataStatusResponse = {
  span: 'DISABLED',
};

/** 1.15 GetDataSamplingResource — 采样数据（有数据） */
export const MOCK_DATA_SAMPLING: IDataSamplingResponse = [
  {
    raw_log: {
      'resource.bk.instance.id': 'demo_web_01',
      'resource.service.name': 'demo_app',
      'resource.telemetry.sdk.language': 'javascript',
      'resource.telemetry.sdk.name': '@opentelemetry/sdk-trace-web',
      'resource.telemetry.sdk.version': '1.21.0',
      span_name: 'HTTP GET /api/v1/resource/list',
      kind: 2,
      'status.code': 0,
      trace_id: 'a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6',
      span_id: '1a2b3c4d5e6f7a8b',
      elapsed_time: 128000,
      start_time: 1713764400000000,
      end_time: 1713764400128000,
      'attributes.http.method': 'GET',
      'attributes.http.url': 'https://demo-app.test.com/api/v1/resource/list',
      'attributes.http.status_code': 200,
      'attributes.http.response_content_length': 1024,
    },
    sampling_time: '2026-04-22 15:00:00',
  },
  {
    raw_log: {
      'resource.bk.instance.id': 'demo_web_02',
      'resource.service.name': 'demo_app',
      'resource.telemetry.sdk.language': 'javascript',
      'resource.telemetry.sdk.name': '@opentelemetry/sdk-trace-web',
      'resource.telemetry.sdk.version': '1.21.0',
      span_name: 'resourceTiming',
      kind: 1,
      'status.code': 0,
      trace_id: 'f6e5d4c3b2a1f0e9d8c7b6a5f4e3d2c1',
      span_id: '8a7b6c5d4e3f2a1b',
      elapsed_time: 56000,
      start_time: 1713764401000000,
      end_time: 1713764401056000,
      'attributes.http.method': 'GET',
      'attributes.http.url': 'https://demo-app.test.com/static/js/app.js',
      'attributes.http.status_code': 200,
      'attributes.http.response_content_length': 204800,
    },
    sampling_time: '2026-04-22 15:00:01',
  },
  {
    raw_log: {
      'resource.bk.instance.id': 'demo_web_01',
      'resource.service.name': 'demo_app',
      'resource.telemetry.sdk.language': 'javascript',
      'resource.telemetry.sdk.name': '@opentelemetry/sdk-trace-web',
      'resource.telemetry.sdk.version': '1.21.0',
      span_name: 'XMLHttpRequest POST',
      kind: 2,
      'status.code': 2,
      trace_id: 'c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6',
      span_id: '2b3c4d5e6f7a8b9c',
      elapsed_time: 3200000,
      start_time: 1713764402000000,
      end_time: 1713764405200000,
      'attributes.http.method': 'POST',
      'attributes.http.url': 'https://demo-app.test.com/api/v1/resource/update',
      'attributes.http.status_code': 500,
      'attributes.http.response_content_length': 256,
    },
    sampling_time: '2026-04-22 15:00:02',
  },
];

/** 1.15 GetDataSamplingResource — 采样数据（空列表） */
export const MOCK_DATA_SAMPLING_EMPTY: IDataSamplingResponse = [];

/** 1.16 GetNoDataStrategyInfoResource — 策略信息（已配置、已启用、有告警图） */
export const MOCK_STRATEGY_INFO: IStrategyData = {
  id: 8992,
  name: 'BKRUM-无数据告警-demo_app-metric',
  alert_status: 1,
  alert_count: 0,
  alert_graph: {
    id: 1,
    title: '告警数量',
    type: 'apdex-chart',
    targets: [
      {
        dataType: 'event',
        datasource: 'time_series',
        api: 'rum_metric.alertQuery',
        data: {
          bk_biz_id: 2,
          app_name: 'demo_app',
          strategy_id: 8992,
        },
      },
    ],
  },
  is_enabled: false,
  notice_group: [
    {
      id: 451,
      name: '运维',
    },
  ],
};

/** 1.16 GetNoDataStrategyInfoResource — 策略信息（已启用、有告警） */
export const MOCK_STRATEGY_INFO_WITH_ALERT: IStrategyData = {
  id: 8993,
  name: 'BKRUM-无数据告警-demo_app-metric',
  alert_status: 2,
  alert_count: 5,
  alert_graph: {
    id: 2,
    title: '告警数量',
    type: 'apdex-chart',
    targets: [
      {
        dataType: 'event',
        datasource: 'time_series',
        api: 'rum_metric.alertQuery',
        data: {
          bk_biz_id: 2,
          app_name: 'demo_app',
          strategy_id: 8993,
        },
      },
    ],
  },
  is_enabled: true,
  notice_group: [
    {
      id: 451,
      name: '运维',
    },
    {
      id: 452,
      name: '开发',
    },
  ],
};

/** 1.16 GetNoDataStrategyInfoResource — 策略信息（未配置告警图） */
export const MOCK_STRATEGY_INFO_NO_GRAPH: IStrategyData = {
  id: 8994,
  name: 'BKRUM-无数据告警-demo_app-metric',
  alert_status: 1,
  alert_count: 0,
  alert_graph: null,
  is_enabled: true,
  notice_group: [
    {
      id: 451,
      name: '运维',
    },
  ],
};

// ===================== Mock 请求函数 =====================

/** 模拟延迟 */
const delay = (ms = 300) => new Promise<void>(resolve => setTimeout(resolve, ms));

/**
 * @description Mock 1.14 GetDataStatusResource — 获取数据状态
 * @param {Record<string, unknown>} _params - 请求参数（bk_biz_id, app_name, start_time, end_time）
 * @returns {Promise<IDataStatusResponse>} 数据状态
 */
export const fetchMockDataStatus = async (_params: Record<string, unknown>): Promise<IDataStatusResponse> => {
  await delay();
  return { ...MOCK_DATA_STATUS_NORMAL };
};

/**
 * @description Mock 1.15 GetDataSamplingResource — 获取数据采样
 * @param {Record<string, unknown>} _params - 请求参数（bk_biz_id, app_name, size?）
 * @returns {Promise<IDataSamplingResponse>} 采样数据列表
 */
export const fetchMockDataSampling = async (_params: Record<string, unknown>): Promise<IDataSamplingResponse> => {
  await delay(500);
  return [...MOCK_DATA_SAMPLING];
};

/**
 * @description Mock 1.16 GetNoDataStrategyInfoResource — 获取无数据策略信息
 * @param {Record<string, unknown>} _params - 请求参数（bk_biz_id, app_name）
 * @returns {Promise<IStrategyData>} 策略数据
 */
export const fetchMockStrategyInfo = async (_params: Record<string, unknown>): Promise<IStrategyData> => {
  await delay(400);
  return {
    ...MOCK_STRATEGY_INFO,
    alert_graph: MOCK_STRATEGY_INFO.alert_graph ? { ...MOCK_STRATEGY_INFO.alert_graph } : null,
  };
};
