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
import type { IRumRawField, IRumRawGroup, IRumRawViewConfig } from '../../typings';

type FieldSeed = [name: string, alias: string, type: IRumRawField['field_type'], extra?: Partial<IRumRawField>];

const STRING_OPERATIONS: IRumRawField['supported_operations'] = [
  { operator: 'equal', label: '=', placeholder: '请输入' },
  { operator: 'not_equal', label: '!=', placeholder: '请输入' },
  { operator: 'include', label: '包含', placeholder: '请输入', wildcard_operator: 'include' },
  { operator: 'exclude', label: '不包含', placeholder: '请输入' },
  { operator: 'exists', label: '存在', placeholder: '' },
  { operator: 'not exists', label: '不存在', placeholder: '' },
];

const NUMBER_OPERATIONS: IRumRawField['supported_operations'] = [
  { operator: 'equal', label: '=', placeholder: '请输入' },
  { operator: 'not_equal', label: '!=', placeholder: '请输入' },
  { operator: 'gt', label: '>', placeholder: '请输入' },
  { operator: 'gte', label: '>=', placeholder: '请输入' },
  { operator: 'lt', label: '<', placeholder: '请输入' },
  { operator: 'lte', label: '<=', placeholder: '请输入' },
];

function createField([name, alias, type, extra]: FieldSeed): IRumRawField {
  const isNumber = ['double', 'integer', 'long'].includes(type);
  return {
    field_name: name,
    field_alias: alias,
    field_type: type,
    is_real: true,
    is_searchable: true,
    is_agg: true,
    is_list: true,
    supported_operations: isNumber ? NUMBER_OPERATIONS : STRING_OPERATIONS,
    ...extra,
  };
}

const GROUP_SEEDS: Array<{
  alias: string;
  fields: FieldSeed[];
  name: string;
  supported_span_types?: string[];
}> = [
  {
    name: 'COMMON',
    alias: '公共字段',
    fields: [
      ['kind', 'Span 类型', 'long'],
      ['span_name', 'Span 名称', 'keyword'],
      [
        'attributes.span_type',
        '数据类型',
        'keyword',
        {
          option_values: [
            { value: 'view', alias: '视图' },
            { value: 'resource', alias: '资源加载' },
            { value: 'error', alias: '错误' },
            { value: 'vital', alias: '网页指标' },
            { value: 'long_task', alias: '长任务' },
            { value: 'action', alias: '用户交互' },
            { value: 'websocket', alias: 'WebSocket' },
            { value: 'custom', alias: '自定义事件' },
          ],
        },
      ],
      ['elapsed_time', '耗时', 'long', { field_unit: 'us' }],
      ['status.code', '状态码', 'long'],
      ['status.message', '状态描述', 'keyword'],
    ],
  },
  {
    name: 'APPLICATION',
    alias: '应用 & 版本',
    fields: [
      ['resource.service.name', '服务名', 'keyword'],
      ['resource.service.version', '版本', 'keyword'],
      ['resource.development.environment', '环境', 'keyword'],
      ['resource.telemetry.sdk.version', 'SDK 版本', 'keyword'],
      ['resource.telemetry.sdk.language', '语言', 'keyword'],
      ['resource.telemetry.sdk.name', 'SDK 名称', 'keyword'],
    ],
  },
  {
    name: 'DEVICE_BROWSER',
    alias: '终端 & 浏览器',
    supported_span_types: ['view', 'resource', 'error', 'action', 'long_task', 'vital', 'websocket'],
    fields: [
      ['resource.device.type', '设备类型', 'keyword'],
      ['resource.user_agent.name', '代理名称', 'keyword'],
      ['resource.user_agent.version', '浏览器版本', 'keyword'],
      ['resource.user_agent.os.name', '操作系统', 'keyword'],
    ],
  },
  {
    name: 'NETWORK',
    alias: '网络 & 地域',
    fields: [
      ['attributes.network.connection.type', '连接类型', 'keyword'],
      ['attributes.network.effective_type', '有效网络质量', 'keyword'],
    ],
  },
  {
    name: 'USER',
    alias: '用户',
    fields: [['attributes.user.id', '用户 ID', 'keyword']],
  },
  {
    name: 'RESOURCE',
    alias: '资源加载',
    supported_span_types: ['resource'],
    fields: [
      [
        'attributes.resource.type',
        '资源类型',
        'keyword',
        {
          option_values: [
            { value: 'xhr' },
            { value: 'fetch' },
            { value: 'script' },
            { value: 'css' },
            { value: 'image' },
          ],
        },
      ],
      ['attributes.url.template', 'URL 模型', 'keyword'],
      ['attributes.http.request.method', 'HTTP 请求方法', 'keyword'],
      ['attributes.http.response.status_code', 'HTTP 响应状态码', 'long'],
      ['attributes.resource.size', '资源大小', 'long', { field_unit: 'bytes' }],
      ['attributes.resource.protocol', '传输协议', 'keyword'],
    ],
  },
  {
    name: 'VIEW',
    alias: '视图',
    supported_span_types: ['view', 'action', 'error'],
    fields: [
      ['attributes.view.referrer', '初始来源页面 URL', 'keyword'],
      ['attributes.view.url_template', '视图路径分组', 'keyword'],
    ],
  },
  {
    name: 'ACTION',
    alias: '用户交互',
    supported_span_types: ['action'],
    fields: [
      ['attributes.action.type', '动作类型', 'keyword'],
      ['attributes.action.target.name', '目标元素名称', 'keyword'],
    ],
  },
  {
    name: 'WEB_VITALS',
    alias: 'Web Vitals（网页指标）',
    supported_span_types: ['vital'],
    fields: [
      ['INP', '交互到下一次绘制', 'double', { field_unit: 'ms', is_real: false, is_list: false }],
      ['LCP', '最大内容绘制', 'double', { field_unit: 'ms', is_real: false, is_list: false }],
      ['FCP', '首次内容绘制', 'double', { field_unit: 'ms', is_real: false, is_list: false }],
      ['TTFB', '首字节耗时', 'double', { field_unit: 'ms', is_real: false, is_list: false }],
      ['CLS', '累计布局偏移', 'double', { field_unit: '', is_real: false, is_list: false }],
    ],
  },
];

/** 只出现在「原始字段」分组、不属于任何业务分组的真实字段 */
const EXTRA_REAL_FIELDS: FieldSeed[] = [
  ['span_id', 'Span ID', 'keyword'],
  ['trace_id', 'Trace ID', 'keyword'],
  ['parent_span_id', '父 Span ID', 'keyword'],
  ['start_time', '开始时间', 'long', { field_unit: 'us' }],
  ['end_time', '时间', 'long', { field_unit: 'us' }],
  ['attributes.session.id', '会话 ID', 'keyword'],
  ['attributes.error.source', '错误来源', 'keyword'],
  ['attributes.error.type', '错误类型', 'keyword'],
  ['attributes.error.message', '错误信息', 'text', { is_agg: false }],
  ['attributes.long_task.name', '长任务名称', 'keyword'],
  ['attributes.long_task.entry_type', '长任务类型', 'keyword'],
  ['attributes.vital.metric', '指标名', 'keyword'],
  ['attributes.vital.value', '指标值', 'double'],
  ['events.name', '事件名', 'keyword'],
  ['events.timestamp', '事件时间', 'long', { field_unit: 'us' }],
  ['events.attributes.exception.type', '异常类型', 'keyword'],
  ['events.attributes.exception.message', '异常信息', 'text', { is_agg: false }],
  ['resource.bk.instance.id', '实例 ID', 'keyword'],
  ['resource.net.host.name', '主机名', 'keyword'],
];

const fields: IRumRawField[] = [
  ...GROUP_SEEDS.flatMap(group => group.fields.map(createField)),
  ...EXTRA_REAL_FIELDS.map(createField),
];

const groups: IRumRawGroup[] = GROUP_SEEDS.map(group => ({
  name: group.name,
  alias: group.alias,
  supported_span_types: group.supported_span_types || [],
  field_names: group.fields.map(([name]) => name),
}));

export const mockViewConfig: IRumRawViewConfig = {
  default_sort: ['-end_time'],
  fields,
  groups,
  display_fields: [
    'span_name',
    'attributes.span_type',
    'end_time',
    'elapsed_time',
    'status.code',
    'attributes.view.url_template',
    'resource.user_agent.name',
    'attributes.user.id',
  ],
  span_type_display_fields: {
    view: [
      'span_name',
      'attributes.span_type',
      'end_time',
      'elapsed_time',
      'attributes.view.url_template',
      'attributes.user.id',
    ],
    resource: [
      'span_name',
      'attributes.span_type',
      'end_time',
      'elapsed_time',
      'attributes.resource.type',
      'attributes.http.request.method',
      'attributes.http.response.status_code',
      'attributes.resource.size',
    ],
    error: [
      'span_name',
      'attributes.span_type',
      'end_time',
      'attributes.error.source',
      'attributes.error.type',
      'attributes.view.url_template',
    ],
    vital: ['span_name', 'attributes.span_type', 'end_time', 'attributes.vital.metric', 'attributes.vital.value'],
    long_task: [
      'span_name',
      'attributes.span_type',
      'end_time',
      'elapsed_time',
      'attributes.long_task.name',
      'attributes.long_task.entry_type',
    ],
    action: [
      'span_name',
      'attributes.span_type',
      'end_time',
      'elapsed_time',
      'attributes.action.type',
      'attributes.action.target.name',
    ],
    websocket: ['span_name', 'attributes.span_type', 'end_time', 'elapsed_time', 'status.code'],
    custom: ['span_name', 'attributes.span_type', 'end_time', 'elapsed_time', 'status.code'],
  },
};
