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

import type { ITraceData } from '../typings';

interface ISpanKindMaps {
  [key: number]: string;
}

export const DEFAULT_TRACE_DATA: ITraceData = {
  original_data: [],
  span_classify: [],
  topo_relation: [],
  topo_nodes: [],
  trace_id: '',
  trace_info: {
    root_span_id: '',
    product_time: 0,
    trace_duration: 0,
    service_count: 0,
    hierarchy_count: 0,
    min_duration: 0,
    max_duration: 0,
    time_error: false,
  },
  streamline_service_topo: {
    nodes: [],
    edges: [],
  },
};

export const SPAN_KIND_MAPS: ISpanKindMaps = {
  0: window.i18n.t('未定义'),
  1: window.i18n.t('内部调用'),
  2: window.i18n.t('同步被调'),
  3: window.i18n.t('同步主调'),
  4: window.i18n.t('异步主调'),
  5: window.i18n.t('异步被调'),
  6: window.i18n.t('推断'),
};

export const SPAN_STATUS_CODE = {
  0: window.i18n.t('未设置'),
  1: window.i18n.t('正常'),
  2: window.i18n.t('异常'),
};

export const SOURCE_CATEGORY_EBPF = 'source_category_ebpf';
export const VIRTUAL_SPAN = 'virtual_span';
export const QUERY_TRACE_RELATION_APP = 'query_trace_relation_app';
export const TRACE_INFO_TOOL_FILTERS = [
  { id: 'duration', label: window.i18n.t('耗时'), show: true, effect: ['timeline', 'topo'] },
  // { id: 'async', label: window.i18n.t('异步调用'), effect: ['timeline', 'topo'] },
  // { id: 'internal', label: window.i18n.t('内部调用'), effect: ['timeline', 'topo'] },
  {
    id: SOURCE_CATEGORY_EBPF,
    label: 'eBPF',
    show: window.apm_ebpf_enabled ?? false,
    effect: ['timeline', 'topo', 'sequence', 'flame'],
    desc: window.i18n.t('安装了eBPF的采集服务就可以展示eBPF相关的数据'),
  },
  {
    id: VIRTUAL_SPAN,
    label: window.i18n.t('推断'),
    show: true,
    effect: ['timeline', 'topo', 'sequence', 'flame'],
    desc: window.i18n.t('通过Span信息推断出DB、中间件、第三方等服务'),
  },
  { id: QUERY_TRACE_RELATION_APP, label: window.i18n.t('跨应用追踪'), show: true, effect: ['timeline'] },
  { id: 'endpoint', label: window.i18n.t('接口'), show: true, effect: ['statistics'] },
  { id: 'service', label: window.i18n.t('服务'), show: true, effect: ['statistics'] },
  { id: 'source', label: window.i18n.t('数据来源'), show: true, effect: ['statistics'] },
  { id: 'spanKind', label: window.i18n.t('Span类型'), show: true, effect: ['statistics'] },
];
