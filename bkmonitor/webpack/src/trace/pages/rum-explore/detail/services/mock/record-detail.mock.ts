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
import { RumSectionTypeEnum } from '../../typings';

import type { IRumDetailItem, IRumRecordDetail } from '../../typings';

/**
 * record_detail 接口的 mock 数据，结构与取值均按《RUM 检索接口协议》2.11 的示例构造。
 * 接口联调完成后把 constants 里的 USE_DETAIL_MOCK 置为 false 即可切回真实接口。
 */

/** 各类型共用的公共信息项 */
const COMMON_ITEMS: IRumDetailItem[] = [
  { field_name: 'app_name', value: 'rum-demo' },
  { field_name: 'attributes.view.url_template', value: '/order/submit' },
  { field_name: 'attributes.session.id', value: 'sess_f3lhlawshdf' },
  { field_name: 'attributes.view.id', value: 'view_f3lhlawshdf' },
  { field_name: 'start_time', value: 1788451565200000 },
  { field_name: 'end_time', value: 1788451565328000 },
  { field_name: 'attributes.user.id', value: 'u_34523452345253' },
  { field_name: 'resource.deployment.environment.name', value: 'prod' },
];

/** 类型项在公共信息里排第一，各类型文案不同 */
const typeItem = (alias: string): IRumDetailItem => ({
  field_name: 'display.span_type',
  field_alias: window.i18n.t('类型') as string,
  alias,
  value: alias,
});

/** 各类型共用的原始 Span 骨架 */
const originData = (spanId: string, spanType: string, spanName: string): Record<string, any> => ({
  span_id: spanId,
  trace_id: '206fa04fb665bf8ef1fba9255b59c3e1',
  span_name: spanName,
  parent_span_id: '',
  start_time: 1788451565200000,
  end_time: 1788451565328000,
  elapsed_time: 128000,
  kind: 3,
  'status.code': 0,
  attributes: {
    span_type: spanType,
    'action.id': '22c3ad4e-4e2d-48e2-9ad9-6b86fc58e5ff',
    'browser.screen.height': 2561,
    'browser.screen.width': 1440,
    'browser.viewport.height': 2425,
    'browser.viewport.width': 1440,
    'session.id': 'sess_f3lhlawshdf',
    'view.id': 'view_f3lhlawshdf',
    'view.url_template': '/order/submit',
    'user.id': 'u_34523452345253',
  },
  resource: {
    'deployment.environment.name': 'production',
    'device.type': 'desktop',
    'service.name': 'bk-monitor',
    'session.sample_rate': 1,
    'telemetry.sdk.language': 'webjs',
    'telemetry.sdk.name': 'opentelemetry',
    'telemetry.sdk.version': '1.9.0',
  },
  links: [
    {
      attributes: {
        format: 'traceparent',
        injected: false,
        traceparent: '00-3f7f7162123123123123a0c6aa3c74d6b1231236cf6fe51d0f5fc-01',
      },
      span_id: '4c6123123123125fc',
      trace_id: '3f7f7162a1231231231231123122358a8',
      trace_state: {},
    },
  ],
  events: [
    {
      name: 'SENT',
      timestamp: 12234523452452000,
      attributes: {
        'exception.message': 'Failed to fetch',
        'exception.stacktrace':
          'TypeError: Failed to fetch\n    at https://example.com/static/js/main.js:2:2968616\n    at https://example.com/static/js/main.js:2:2954905\n    at Generator.next (<anonymous>)',
        'exception.type': 'TypeError',
      },
    },
    {
      name: 'RECEIVED',
      timestamp: 12234523452462000,
      attributes: { 'exception.type': 'TypeError' },
    },
  ],
});

/** Resource（XHR / Fetch） */
const RESOURCE_FETCH: IRumRecordDetail = {
  span_id: '7d2f09b6f8bc31aa',
  origin_data: originData('7d2f09b6f8bc31aa', 'resource', 'browser.resource'),
  overview: {
    title: 'POST /api/orders',
    badges: [
      { field_name: 'elapsed_time', value: 128000 },
      { field_name: 'attributes.resource.type', value: 'fetch' },
      { field_name: 'attributes.http.response.status_code', value: 200 },
    ],
    items: [typeItem('Resource(fetch)'), ...COMMON_ITEMS],
  },
  sections: [
    {
      key: 'key_info',
      type: RumSectionTypeEnum.SUMMARY_CARDS,
      data: {
        request: {
          'attributes.http.request.method': 'POST',
          'attributes.url.template': '/api/orders',
          'attributes.url.full': 'https://example.com/api/orders',
          'attributes.server.address': 'example.com',
        },
        duration: { elapsed_time: 18530 },
        http_result: { 'attributes.http.response.status_code': 200, 'attributes.outcome.type': 'success' },
        transfer: {
          'display.compression_ratio': 0,
          'attributes.resource.transfer_size': 415,
          'attributes.resource.encoded_body_size': 415,
          'attributes.resource.decoded_body_size': 415,
        },
      },
    },
    {
      key: 'loading_timing',
      type: RumSectionTypeEnum.WATERFALL,
      data: {
        unit: 'ms',
        total_duration: 122.2,
        phases: [
          { key: 'prepare', alias: window.i18n.t('浏览器准备') as string, start: 0, duration: 1 },
          { key: 'dns', alias: 'DNS', start: 1, duration: 0 },
          { key: 'connect', alias: 'TCP', start: 1, duration: 0 },
          { key: 'tls', alias: 'TLS', start: 1, duration: 0 },
          { key: 'first_byte', alias: window.i18n.t('等待 TTFB') as string, start: 1, duration: 13.8 },
          { key: 'download', alias: window.i18n.t('内容下载') as string, start: 14.8, duration: 2.4 },
        ],
      },
    },
  ],
};

/** Resource（其他资源） */
const RESOURCE_OTHER: IRumRecordDetail = {
  span_id: '8e301ac709bd42bb',
  origin_data: originData('8e301ac709bd42bb', 'resource', 'browser.resource'),
  overview: {
    title: 'db.svg',
    badges: [
      { field_name: 'elapsed_time', value: 60300 },
      { field_name: 'attributes.resource.type', value: 'script' },
      { field_name: 'attributes.http.response.status_code', value: 200 },
    ],
    items: [typeItem('Resource (Image)'), ...COMMON_ITEMS],
  },
  sections: [
    {
      key: 'key_info',
      type: RumSectionTypeEnum.SUMMARY_CARDS,
      data: {
        http_result: { 'attributes.http.response.status_code': 200, 'attributes.outcome.type': 'success' },
        duration: { elapsed_time: 60300 },
        transfer: {
          'display.compression_ratio': 0.689,
          'attributes.resource.transfer_size': 0,
          'attributes.resource.encoded_body_size': 280833,
          'attributes.resource.decoded_body_size': 903000,
        },
        delivery: { 'attributes.resource.delivery_type': 'cache', 'attributes.resource.cache.hit': true },
        blocking: { 'attributes.resource.render_blocking_status': 'non-blocking' },
      },
    },
    {
      key: 'resource_info',
      type: RumSectionTypeEnum.SUMMARY_CARDS,
      items: [
        { field_name: 'attributes.resource.type', field_alias: window.i18n.t('资源类型') as string, value: 'img' },
        { field_name: 'attributes.url.template', field_alias: window.i18n.t('URL 模版') as string, value: '' },
        {
          field_name: 'attributes.server.address',
          field_alias: window.i18n.t('服务端地址') as string,
          value: 'example.com',
        },
        { field_name: 'attributes.http.request.method', field_alias: window.i18n.t('请求方法') as string, value: '' },
        { field_name: 'attributes.resource.protocol', field_alias: window.i18n.t('网络协议') as string, value: '' },
      ],
    },
    {
      key: 'loading_timing',
      type: RumSectionTypeEnum.WATERFALL,
      data: {
        unit: 'ms',
        total_duration: 122.2,
        phases: [
          { key: 'prepare', alias: window.i18n.t('浏览器准备') as string, start: 0, duration: 1 },
          { key: 'dns', alias: 'DNS', start: 1, duration: 0 },
          { key: 'connect', alias: 'TCP', start: 1, duration: 0 },
          { key: 'tls', alias: 'TLS', start: 1, duration: 0 },
          { key: 'first_byte', alias: window.i18n.t('等待 TTFB') as string, start: 1, duration: 13.8 },
          { key: 'download', alias: window.i18n.t('内容下载') as string, start: 14.8, duration: 2.4 },
        ],
      },
    },
  ],
};

/** Action */
const ACTION: IRumRecordDetail = {
  span_id: 'e121536e5ae785a0',
  origin_data: originData('e121536e5ae785a0', 'action', 'browser.action'),
  overview: {
    title: 'click.submit-btn',
    badges: [
      { field_name: 'elapsed_time', value: 1120000 },
      { field_name: 'attributes.action.type', value: 'click' },
      { field_name: 'attributes.outcome.type', value: 'warning' },
    ],
    items: [typeItem('Action'), ...COMMON_ITEMS],
  },
  sections: [
    {
      key: 'key_info',
      type: RumSectionTypeEnum.SUMMARY_CARDS,
      data: {
        interaction: { 'attributes.action.type': 'click', 'attributes.action.id': 'action-001' },
        target: { 'attributes.action.target.name': 'button.submit-btn', 'attributes.action.target.tag': 'button' },
      },
    },
  ],
};

/** Long Task */
const LONG_TASK: IRumRecordDetail = {
  span_id: 'c49ddfc2ac5214d7',
  origin_data: originData('c49ddfc2ac5214d7', 'long_task', 'browser.long_task'),
  overview: {
    title: 'longTask',
    badges: [
      { field_name: 'elapsed_time', value: 1120000 },
      { field_name: 'attributes.outcome.type', value: 'warning' },
    ],
    items: [typeItem('Long Task'), ...COMMON_ITEMS],
  },
  sections: [
    {
      key: 'key_info',
      type: RumSectionTypeEnum.SUMMARY_CARDS,
      data: {
        duration: { elapsed_time: 123500, 'attributes.long_task.blocking_duration': 42.5 },
        action: { 'attributes.action.id': '' },
        attribution: {
          'attributes.long_task.entry_type': 'long-animation-frame',
          'attributes.long_task.name': 'long-animation-frame',
        },
      },
    },
  ],
};

/** Error */
const ERROR: IRumRecordDetail = {
  span_id: '9d199175096474e4',
  origin_data: originData('9d199175096474e4', 'error', 'browser.error'),
  overview: {
    title: "TypeError: Cannot read properties of undefined (reading 'name')",
    badges: [
      { field_name: 'elapsed_time', value: 1120000 },
      { field_name: 'attributes.outcome.type', value: 'error' },
    ],
    items: [typeItem('JS Error'), ...COMMON_ITEMS],
  },
  sections: [
    {
      key: 'key_info',
      type: RumSectionTypeEnum.SUMMARY_CARDS,
      data: {
        error_type: { 'events.attributes.exception.type': 'TypeError' },
        source: {
          'attributes.code.filepath': 'https://example.com/static/js/Submit.tsx',
          'attributes.code.lineno': 42,
          'attributes.code.column': 3,
        },
      },
    },
  ],
};

/** Vital */
const VITAL: IRumRecordDetail = {
  span_id: 'ea1ae6490e17fd9d',
  origin_data: originData('ea1ae6490e17fd9d', 'vital', 'browser.vital'),
  overview: {
    title: 'LCP',
    badges: [
      { field_name: 'attributes.vital.value', value: 2840 },
      { field_name: 'display.rating_level', alias: window.i18n.t('需改进') as string, value: 'needs_improvement' },
    ],
    items: [typeItem('Web Vital'), ...COMMON_ITEMS],
  },
  sections: [
    {
      key: 'vital_rating',
      type: RumSectionTypeEnum.RATING_BAR,
      data: {
        'attributes.vital.metric': 'lcp',
        'attributes.vital.value': 2840,
        'display.rating_config': [
          { rating: 'good', value: 2500, alias: window.i18n.t('良好') as string },
          { rating: 'needs_improvement', value: 4000, alias: window.i18n.t('需改进') as string },
          { rating: 'poor', alias: window.i18n.t('差') as string },
        ],
      },
    },
  ],
};

/** 按 span 类型索引的 mock 详情，resource 默认返回 xhr/fetch 形态 */
const MOCK_BY_SPAN_TYPE: Record<string, IRumRecordDetail> = {
  resource: RESOURCE_FETCH,
  action: ACTION,
  long_task: LONG_TASK,
  error: ERROR,
  vital: VITAL,
};

/**
 * @description 取指定 span 类型的 mock 详情
 * @param spanType span 类型，未登记时回退到 Resource（其他资源）形态
 * @param recordId 当前记录 ID，回填到返回结构里保持与入参一致
 */
export function getMockRecordDetail(spanType: string, recordId: string): IRumRecordDetail {
  const detail = MOCK_BY_SPAN_TYPE[spanType] || RESOURCE_OTHER;
  return {
    ...detail,
    span_id: recordId || detail.span_id,
    origin_data: { ...detail.origin_data, span_id: recordId || detail.span_id },
  };
}
