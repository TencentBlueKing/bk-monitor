/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
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
const traceListSetting = {
  fields: [
    {
      label: 'Trace ID',
      field: 'traceID',
      disabled: true,
    },
    {
      label: `${window.i18n.t('开始时间')}`,
      field: 'min_start_time',
    },
    {
      label: `${window.i18n.t('根Span')}`,
      field: 'root_span_name',
    },
    {
      label: `${window.i18n.t('入口服务')}`,
      field: 'entryService',
    },
    {
      label: `${window.i18n.t('入口接口')}`,
      field: 'root_service_span_name',
    },
    {
      label: `${window.i18n.t('调用类型')}`,
      field: 'root_service_category',
    },
    {
      label: `${window.i18n.t('状态码')}`,
      field: 'statusCode',
    },
    {
      label: `${window.i18n.t('耗时')}`,
      field: 'trace_duration',
    },
    {
      label: `${window.i18n.t('同步Span数量')}`,
      field: 'kind_statistics.sync',
    },
    {
      label: `${window.i18n.t('异步Span数量')}`,
      field: 'kind_statistics.async',
    },
    {
      label: `${window.i18n.t('内部Span数量')}`,
      field: 'kind_statistics.interval',
    },
    {
      label: `${window.i18n.t('未知Span数量')}`,
      field: 'kind_statistics.unspecified',
    },
    {
      label: `${window.i18n.t('DB 数量')}`,
      field: 'category_statistics.db',
    },
    {
      label: `${window.i18n.t('Messaging 数量')}`,
      field: 'category_statistics.messaging',
    },
    {
      label: `${window.i18n.t('HTTP 数量')}`,
      field: 'category_statistics.http',
    },
    {
      label: `${window.i18n.t('RPC 数量')}`,
      field: 'category_statistics.rpc',
    },
    {
      label: `${window.i18n.t('Async 数量')}`,
      field: 'category_statistics.async_backend',
    },
    {
      label: `${window.i18n.t('Other 数量')}`,
      field: 'category_statistics.other',
    },
    {
      label: `${window.i18n.t('Span 数量')}`,
      field: 'span_count',
    },
    {
      label: `${window.i18n.t('Span 层数')}`,
      field: 'hierarchy_count',
    },
    {
      label: `${window.i18n.t('服务数量')}`,
      field: 'service_count',
    },
  ],
  checked: [
    'traceID',
    'min_start_time',
    'trace_duration',
    'entryService',
    'root_span_name',
    'root_service_span_name',
    'statusCode',
    'root_service_category',
    'hierarchy_count',
    'service_count',
  ],
  limit: 0,
  size: 'medium',
  sizeList: [],
  showLineHeight: false,
};

// traceListSetting.fields.forEach((item) => {
//   traceListSetting.checked.push(item.field);
// });

const spanListSetting = {
  fields: [
    {
      label: 'Span ID',
      field: 'span_id',
      disabled: true,
    },
    {
      label: `${window.i18n.t('接口名称')}`,
      field: 'span_name',
    },
    {
      label: `${window.i18n.t('开始时间')}`,
      field: 'start_time',
    },
    {
      label: `${window.i18n.t('结束时间')}`,
      field: 'end_time',
    },
    {
      label: `${window.i18n.t('耗时')}`,
      field: 'elapsed_time',
    },
    {
      label: `${window.i18n.t('状态')}`,
      field: 'status_code',
    },
    {
      label: `${window.i18n.t('类型')}`,
      field: 'kind',
    },
    {
      label: `${window.i18n.t('所属服务')}`,
      field: 'resource.service.name',
    },
    {
      label: `${window.i18n.t('实例 ID')}`,
      field: 'resource.bk.instance.id',
    },
    {
      label: `${window.i18n.t('SDK 名称')}`,
      field: 'resource.telemetry.sdk.name',
    },
    {
      label: `${window.i18n.t('SDK 版本')}`,
      field: 'resource.telemetry.sdk.version',
    },
    {
      label: `${window.i18n.t('所属Trace')}`,
      field: 'trace_id',
    },
  ],
  checked: ['span_id', 'span_name', 'start_time', 'end_time', 'elapsed_time', 'status_code', 'kind', 'trace_id'],
  limit: 0,
  size: 'medium',
  sizeList: [],
  showLineHeight: false,
};

const interfaceStatisticsSetting = {
  fields: [
    {
      label: `${window.i18n.t('接口名')}`,
      field: 'span_name',
      disabled: true,
    },
    {
      label: `${window.i18n.t('所属Service')}`,
      field: 'service_name',
    },
    {
      label: `${window.i18n.t('来源类型')}`,
      field: 'source',
    },
    {
      label: `${window.i18n.t('接口类型')}`,
      field: 'kind',
    },
    {
      label: `${window.i18n.t('Span数量')}`,
      field: 'span_count',
    },
    {
      label: `${window.i18n.t('错误数')}`,
      field: 'error_count',
    },
    {
      label: `${window.i18n.t('错误率')}`,
      field: 'error_rate',
    },
    {
      label: `${window.i18n.t('平均耗时')}`,
      field: 'avg_duration',
    },
    {
      label: `${window.i18n.t('P90耗时')}`,
      field: 'p90_duration',
    },
    {
      label: `${window.i18n.t('P50耗时')}`,
      field: 'p50_duration',
    },
  ],
  checked: [
    'kind',
    'span_name',
    'service_name',
    'span_count',
    'error_count',
    'avg_duration',
    'p90_duration',
    'p50_duration',
  ],
  limit: 0,
  size: 'medium',
  sizeList: [],
  showLineHeight: false,
};

const serviceStatisticsSetting = {
  fields: [
    {
      label: 'Service',
      field: 'service_name',
    },
    {
      label: `${window.i18n.t('服务类型')}`,
      field: 'kind',
    },
    {
      label: `${window.i18n.t('Span数量')}`,
      field: 'span_count',
    },
    {
      label: `${window.i18n.t('错误数')}`,
      field: 'error_count',
    },
    {
      label: `${window.i18n.t('错误率')}`,
      field: 'error_rate',
    },
    {
      label: `${window.i18n.t('平均耗时')}`,
      field: 'avg_duration',
    },
    {
      label: `${window.i18n.t('P90耗时')}`,
      field: 'p90_duration',
    },
    {
      label: `${window.i18n.t('P50耗时')}`,
      field: 'p50_duration',
    },
  ],
  checked: [
    'service_name',
    'kind',
    'span_count',
    'error_count',
    'error_rate',
    'avg_duration',
    'p90_duration',
    'p50_duration',
  ],
  limit: 0,
  size: 'medium',
  sizeList: [],
  showLineHeight: false,
};

// spanListSetting.fields.forEach((item) => {
//   spanListSetting.checked.push(item.field);
// });

const statisticTableSetting = {
  fields: [
    {
      label: `${window.i18n.t('接口')}`,
      field: 'span_name',
    },
    {
      label: `${window.i18n.t('服务')}`,
      field: 'resource.service.name',
    },
    {
      label: `${window.i18n.t('最大时间')}`,
      field: 'max_duration',
    },
    {
      label: `${window.i18n.t('最小时间')}`,
      field: 'min_duration',
    },
    {
      label: `${window.i18n.t('总时间')}`,
      field: 'sum_duration',
    },
    {
      label: `${window.i18n.t('CP95')}`,
      field: 'P95',
    },
    {
      label: `${window.i18n.t('总数')}`,
      field: 'count',
    },
  ],
  checked: ['span_name', 'resource.service.name', 'max_duration', 'min_duration', 'sum_duration', 'P95', 'count'],
  limit: 0,
  size: 'medium',
  sizeList: [],
  showLineHeight: false,
};

const statisticDiffTableSetting = {
  fields: [
    {
      label: `${window.i18n.t('接口')}`,
      field: 'span_name',
    },
    {
      label: `${window.i18n.t('服务')}`,
      field: 'resource.service.name',
    },
    {
      label: `${window.i18n.t('最大时间')}`,
      field: 'max_duration',
    },
    {
      label: `${window.i18n.t('最小时间')}`,
      field: 'min_duration',
    },
    {
      label: `${window.i18n.t('总时间')}`,
      field: 'sum_duration',
    },
    {
      label: `${window.i18n.t('CP95')}`,
      field: 'P95',
    },
    {
      label: `${window.i18n.t('总数')}`,
      field: 'count',
    },
  ],
  checked: ['span_name', 'resource.service.name', 'max_duration', 'min_duration', 'sum_duration', 'P95', 'count'],
  limit: 0,
  size: 'medium',
  sizeList: [],
  showLineHeight: false,
};

export {
  interfaceStatisticsSetting,
  serviceStatisticsSetting,
  spanListSetting,
  statisticDiffTableSetting,
  statisticTableSetting,
  traceListSetting,
};
