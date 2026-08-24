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
import type { IRumSpanRecord } from '../../typings';

/** 每种 span 类型的样例数据，字段取值参考设计稿中的表格示例 */
const SPAN_TYPE_SEEDS: Array<{
  extra?: Record<string, unknown>;
  names: string[];
  type: string;
}> = [
  {
    type: 'websocket',
    names: ['POST /query/ts', 'PATCH /user/settings', 'GET /static/js/legacy.js', 'DELETE /api/sessions/123'],
  },
  {
    type: 'custom',
    names: ['SELECT bk_metrics', 'memoryLeakDetected', 'resourceLoadTimeout'],
  },
  {
    type: 'action',
    names: ['click .submit-btn', 'submit form #login', 'hover .tooltip-icon', 'click button #subscribe'],
    extra: { 'attributes.action.type': 'click', 'attributes.action.target.name': 'submit-btn' },
  },
  {
    type: 'long_task',
    names: ['longTask'],
    extra: { 'attributes.long_task.name': 'self', 'attributes.long_task.entry_type': 'longtask' },
  },
  {
    type: 'view',
    names: ['documentLoad', 'routeChange /home → /order/list', 'routeChange /profile → /settings'],
  },
  {
    type: 'error',
    names: ["TypeError: cannot read 'name'", 'ReferenceError: undefinedVariable'],
    extra: { 'attributes.error.source': 'source', 'attributes.error.type': 'TypeError' },
  },
  {
    type: 'resource',
    names: ['GET /assets/images/logo.svg', 'GET /static/css/main.css'],
    extra: {
      'attributes.resource.type': 'xhr',
      'attributes.http.request.method': 'GET',
      'attributes.http.response.status_code': 200,
      'attributes.resource.size': 20480,
      'attributes.resource.protocol': 'http/1.1',
    },
  },
  {
    type: 'vital',
    names: ['LCP', 'FCP'],
    extra: { 'attributes.vital.metric': 'LCP', 'attributes.vital.value': 1280 },
  },
];

const BROWSERS = [
  'Chrome 89',
  'Safari 17',
  'Firefox 113',
  'Edge 120',
  'Brave 1.49',
  'Vivaldi 6.3',
  'Samsung Internet 21',
  'Internet Explorer 11',
  'UC Browser 13',
  'Maxthon 8',
];
const USERS = ['harakoyang', 'carnielu', 'daisyhong', 'eilanzhang', 'miffyyang', 'kaichunwang', 'edwinwu', 'nekzhang'];
const VIEWS = ['/order/submit', '/order/list', '/order/detail', '/user/profile'];
/** 覆盖绿 / 橙 / 红三档着色 */
const DURATIONS_MS = [140, 180, 530, 2354, 95, 234, 875, 2980, 4321, 2352];
const STATUS_CODES = [1, 1, 0, 2, 1, 1, 1, 0, 2, 1];

/** 按索引生成稳定的单条记录，保证滚动加载时不会出现重复或抖动的数据 */
function createRecord(index: number, endTime: number): IRumSpanRecord {
  const seed = SPAN_TYPE_SEEDS[index % SPAN_TYPE_SEEDS.length];
  const spanName = seed.names[index % seed.names.length];
  const elapsedTime = DURATIONS_MS[index % DURATIONS_MS.length] * 1000;
  const end = (endTime - index * 37) * 1e6;

  return {
    span_id: hexId(index + 1, 16),
    trace_id: hexId(index + 7, 32),
    parent_span_id: index % 4 === 0 ? '' : hexId(index + 13, 16),
    span_name: spanName,
    kind: 3,
    start_time: end - elapsedTime,
    end_time: end,
    elapsed_time: elapsedTime,
    'status.code': STATUS_CODES[index % STATUS_CODES.length],
    'status.message': '',
    'attributes.span_type': seed.type,
    'attributes.view.url_template': VIEWS[index % VIEWS.length],
    'attributes.view.referrer': `https://demo.bkmonitor.com${VIEWS[(index + 1) % VIEWS.length]}`,
    'attributes.user.id': USERS[index % USERS.length],
    'attributes.session.id': hexId(index + 21, 12),
    'attributes.url.template': VIEWS[index % VIEWS.length],
    'attributes.network.connection.type': index % 3 === 0 ? 'wifi' : '4g',
    'attributes.network.effective_type': index % 3 === 0 ? '4g' : '3g',
    'resource.user_agent.name': BROWSERS[index % BROWSERS.length],
    'resource.user_agent.version': `${89 + (index % 30)}`,
    'resource.user_agent.os.name': index % 2 === 0 ? 'Windows' : 'macOS',
    'resource.device.type': index % 5 === 0 ? 'mobile' : 'desktop',
    'resource.service.name': 'rum-demo',
    'resource.service.version': '1.2.0',
    'resource.development.environment': 'production',
    'resource.telemetry.sdk.name': 'bk-rum-web',
    'resource.telemetry.sdk.version': '2.3.1',
    'resource.telemetry.sdk.language': 'javascript',
    'resource.bk.instance.id': `instance-${index % 8}`,
    'resource.net.host.name': 'demo.bkmonitor.com',
    'events.name': 'exception',
    'events.timestamp': end,
    'events.attributes.exception.type': 'TypeError',
    'events.attributes.exception.message': "cannot read 'name' of undefined",
    ...seed.extra,
  };
}

function hexId(seed: number, length: number) {
  let text = '';
  let value = seed * 2654435761;
  while (text.length < length) {
    value = (value * 1103515245 + 12345) % 2 ** 31;
    text += value.toString(16);
  }
  return text.slice(0, length);
}

/** 模拟数据总量，用于验证滚动加载到底的表现 */
const MOCK_TOTAL = 187;

export function mockRecordList(params: {
  endTime: number;
  limit: number;
  offset: number;
  spanType?: string;
}): IRumSpanRecord[] {
  const { offset, limit, endTime, spanType } = params;
  const all = Array.from({ length: MOCK_TOTAL }, (_, index) => createRecord(index, endTime));
  const matched = spanType ? all.filter(item => item['attributes.span_type'] === spanType) : all;
  return matched.slice(offset, offset + limit);
}
