/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
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

import { h } from 'vue';

import type { ExploreTableColumnTypeEnum, GetTableCellRenderValue } from './typing';

export const TABLE_DEFAULT_CONFIG = Object.freeze({
  tableConfig: {
    resizable: true,
    ellipsis: false,
    ellipsisTitle: false,
    align: 'left',
    emptyPlaceholder: '--',
  },
  traceConfig: {
    displayFields: [
      'trace_id',
      'min_start_time',
      'root_span_name',
      'root_service',
      'root_service_span_name',
      'root_service_category',
      'root_service_status_code',
      'trace_duration',
      'hierarchy_count',
      'service_count',
    ],
  },
  spanConfig: {
    displayFields: [
      'span_id',
      'span_name',
      'resource.service.name',
      'start_time',
      'end_time',
      'elapsed_time',
      'status.code',
      'kind',
      'trace_id',
    ],
  },
} as const);

/** 启用文本省略hover弹出 popover 内容的单元格类名 */
export const ENABLED_TABLE_ELLIPSIS_CELL_CLASS_NAME = 'explore-text-ellipsis';

/** 启用表格表头hover弹出列描述 popover 列的类名 */
export const ENABLED_TABLE_DESCRIPTION_HEADER_CLASS_NAME = 'explore-table-header-description';

/** 启用表格单元格内容点击能够打开条件设置 conditionMenu 弹窗类名 */
export const ENABLED_TABLE_CONDITION_MENU_CLASS_NAME = 'explore-table-condition-menu';

/** trace检索table展示字段列配置缓存key后缀 */
export const TABLE_DISPLAY_COLUMNS_FIELD_SUFFIX = 'TRACE_EXPLORE_TABLE_DISPLAY_COLUMNS';

/** 可以进行排序的字段类型 */
export const CAN_TABLE_SORT_FIELD_TYPES = new Set(['integer', 'long', 'double', 'date']);

/** 内部调用Icon */
export const LocalInvokerIcon = h(
  'svg',
  {
    width: '22px',
    height: '16px',
    viewBox: '0 0 22 16',
    xmlns: 'http://www.w3.org/2000/svg',
  },
  [
    h(
      'g',
      {
        stroke: 'none',
        'stroke-width': '1',
        fill: 'none',
        'fill-rule': 'evenodd',
      },
      [
        h('path', {
          d: 'M7,13.5 L3,10 L7,6.5 L7,9.5 L15,9.5 C16.3807119,9.5 17.5,8.38071187 17.5,7 C17.5,5.61928813 16.3807119,4.5 15,4.5 L9.42939431,4.5 L9.42939431,3.5 L15,3.5 C16.9329966,3.5 18.5,5.06700338 18.5,7 C18.5,8.93299662 16.9329966,10.5 15,10.5 L7,10.5 L7,13.5 Z',
          fill: '#4D4F56',
        }),
      ]
    ),
  ]
);

/** 同步-被调Icon */
export const SyncCalledIcon = h(
  'svg',
  {
    width: '22px',
    height: '16px',
    viewBox: '0 0 22 16',
    xmlns: 'http://www.w3.org/2000/svg',
  },
  [
    h(
      'g',
      {
        stroke: 'none',
        'stroke-width': '1',
        fill: 'none',
        'fill-rule': 'evenodd',
      },
      [
        h('path', {
          d: 'M7.9937199,4.5 L12,8 L7.9937199,11.5 L7.9928403,8.5 L0.0188403041,8.5 L0.0188403041,7.5 L7.9928403,7.5 L7.9937199,4.5 Z',
          fill: '#4D4F56',
        }),
        h('path', {
          d: 'M21,3 C21.5522847,3 22,3.44771525 22,4 L22,12 C22,12.5522847 21.5522847,13 21,13 L13,13 C12.4477153,13 12,12.5522847 12,12 L12,4 C12,3.44771525 12.4477153,3 13,3 L21,3 Z M18.776,3.932 L17.944,3.932 L17.944,4.804 L16.184,4.804 L16.184,7.676 C16.168,8.892 15.896,9.908 15.368,10.716 L16.048,11.308 C16.656,10.324 16.968,9.14 16.984,7.756 L17.184,7.756 C17.352,8.476 17.68,9.124 18.176,9.708 C17.76,10.076 17.24,10.372 16.624,10.604 L17.04,11.348 C17.72,11.084 18.296,10.74 18.768,10.308 C19.192,10.692 19.712,11.036 20.32,11.348 L20.776,10.604 C20.208,10.348 19.712,10.06 19.296,9.724 C19.728,9.164 20.016,8.492 20.16,7.708 L20.16,6.988 L18.776,6.988 L18.776,5.572 L19.672,5.572 C19.608,5.876 19.536,6.148 19.448,6.388 L20.208,6.604 C20.344,6.14 20.44,5.668 20.496,5.204 L20.496,4.804 L18.776,4.804 L18.776,3.932 Z M14.728,3.908 L13.936,4.124 C14.064,4.436 14.176,4.756 14.288,5.092 L13.456,5.092 L13.456,5.852 L14.96,5.852 C14.664,6.652 14.104,7.476 13.288,8.324 L13.544,9.172 C13.768,8.948 13.976,8.716 14.184,8.492 L14.184,11.34 L14.984,11.34 L14.984,8.356 C15.192,8.628 15.392,8.94 15.6,9.292 L16.056,8.596 C15.912,8.404 15.76,8.228 15.608,8.06 C15.8,7.892 15.976,7.676 16.136,7.412 L15.664,6.948 C15.512,7.228 15.352,7.452 15.184,7.628 C15.12,7.564 15.048,7.508 14.984,7.452 L14.984,7.428 C15.336,6.884 15.592,6.332 15.752,5.772 L15.752,5.092 L15.096,5.092 C15.008,4.732 14.888,4.34 14.728,3.908 Z M19.384,7.756 C19.24,8.276 19.008,8.74 18.696,9.156 C18.336,8.74 18.08,8.276 17.936,7.756 L19.384,7.756 Z M17.944,5.572 L17.944,6.988 L16.984,6.988 L16.984,5.572 L17.944,5.572 Z',
          fill: '#F59500',
        }),
      ]
    ),
  ]
);

/** 同步-主调Icon */
export const SyncInvokerIcon = h(
  'svg',
  {
    width: '22px',
    height: '16px',
    viewBox: '0 0 22 16',
    xmlns: 'http://www.w3.org/2000/svg',
  },
  [
    h(
      'g',
      {
        stroke: 'none',
        'stroke-width': '1',
        fill: 'none',
        'fill-rule': 'evenodd',
      },
      [
        h(
          'g',
          {
            transform: 'translate(0, 3)',
          },
          [
            h('path', {
              d: 'M17.9937199,1.5 L22,5 L17.9937199,8.5 L17.9928403,5.5 L10.0188403,5.5 L10.0188403,4.5 L17.9928403,4.5 L17.9937199,1.5 Z',
              fill: '#4D4F56',
            }),
            h('path', {
              d: 'M9,0 C9.55228475,-1.01453063e-16 10,0.44771525 10,1 L10,9 C10,9.55228475 9.55228475,10 9,10 L1,10 C0.44771525,10 3.38176876e-17,9.55228475 0,9 L0,1 C-6.76353751e-17,0.44771525 0.44771525,6.76353751e-17 1,0 L9,0 Z M4.928,0.892 L4.112,1.116 C4.272,1.46 4.424,1.82 4.552,2.196 L1.696,2.196 L1.696,3.012 L4.576,3.012 L4.576,4.588 L2.088,4.588 L2.088,5.38 L4.576,5.38 L4.576,7.252 L1.424,7.252 L1.424,8.068 L8.584,8.068 L8.584,7.252 L5.424,7.252 L5.424,5.38 L7.92,5.38 L7.92,4.588 L5.424,4.588 L5.424,3.012 L8.312,3.012 L8.312,2.196 L5.368,2.196 C5.264,1.804 5.12,1.372 4.928,0.892 Z',
              fill: '#3A84FF',
            }),
          ]
        ),
      ]
    ),
  ]
);

/** 异步-被调Icon */
export const AsyncCalledIcon = h(
  'svg',
  {
    width: '22px',
    height: '16px',
    viewBox: '0 0 22 16',
    xmlns: 'http://www.w3.org/2000/svg',
  },
  [
    h(
      'g',
      {
        stroke: 'none',
        'stroke-width': '1',
        fill: 'none',
        'fill-rule': 'evenodd',
      },
      [
        h('path', {
          d: 'M7.97491897,4.5 L7.97491897,11.5 L11.974919,8 L7.97491897,4.5 Z M1,7.50733511 L3,7.50733511 L3,8.50733511 L1,8.50733511 Z M4.97491897,7.5 L6.97491897,7.5 L6.97491897,8.5 L4.97491897,8.5 Z',
          fill: '#4D4F56',
        }),
        h('path', {
          d: 'M21,3 C21.5522847,3 22,3.44771525 22,4 L22,12 C22,12.5522847 21.5522847,13 21,13 L13,13 C12.4477153,13 12,12.5522847 12,12 L12,4 C12,3.44771525 12.4477153,3 13,3 L21,3 Z M18.776,3.932 L17.944,3.932 L17.944,4.804 L16.184,4.804 L16.184,7.676 C16.168,8.892 15.896,9.908 15.368,10.716 L16.048,11.308 C16.656,10.324 16.968,9.14 16.984,7.756 L17.184,7.756 C17.352,8.476 17.68,9.124 18.176,9.708 C17.76,10.076 17.24,10.372 16.624,10.604 L17.04,11.348 C17.72,11.084 18.296,10.74 18.768,10.308 C19.192,10.692 19.712,11.036 20.32,11.348 L20.776,10.604 C20.208,10.348 19.712,10.06 19.296,9.724 C19.728,9.164 20.016,8.492 20.16,7.708 L20.16,6.988 L18.776,6.988 L18.776,5.572 L19.672,5.572 C19.608,5.876 19.536,6.148 19.448,6.388 L20.208,6.604 C20.344,6.14 20.44,5.668 20.496,5.204 L20.496,4.804 L18.776,4.804 L18.776,3.932 Z M14.728,3.908 L13.936,4.124 C14.064,4.436 14.176,4.756 14.288,5.092 L13.456,5.092 L13.456,5.852 L14.96,5.852 C14.664,6.652 14.104,7.476 13.288,8.324 L13.544,9.172 C13.768,8.948 13.976,8.716 14.184,8.492 L14.184,11.34 L14.984,11.34 L14.984,8.356 C15.192,8.628 15.392,8.94 15.6,9.292 L16.056,8.596 C15.912,8.404 15.76,8.228 15.608,8.06 C15.8,7.892 15.976,7.676 16.136,7.412 L15.664,6.948 C15.512,7.228 15.352,7.452 15.184,7.628 C15.12,7.564 15.048,7.508 14.984,7.452 L14.984,7.428 C15.336,6.884 15.592,6.332 15.752,5.772 L15.752,5.092 L15.096,5.092 C15.008,4.732 14.888,4.34 14.728,3.908 Z M19.384,7.756 C19.24,8.276 19.008,8.74 18.696,9.156 C18.336,8.74 18.08,8.276 17.936,7.756 L19.384,7.756 Z M17.944,5.572 L17.944,6.988 L16.984,6.988 L16.984,5.572 L17.944,5.572 Z',
          fill: '#F59500',
        }),
      ]
    ),
  ]
);

/** 异步-调用方Icon */
export const AsyncInvokerIcon = h(
  'svg',
  {
    width: '22px',
    height: '16px',
    viewBox: '0 0 22 16',
    xmlns: 'http://www.w3.org/2000/svg',
  },
  [
    h(
      'g',
      {
        stroke: 'none',
        'stroke-width': '1',
        fill: 'none',
        'fill-rule': 'evenodd',
      },
      [
        h('path', {
          d: 'M11,7.50733511 L13,7.50733511 L13,8.50733511 L11,8.50733511 Z M14.974919,7.5 L16.974919,7.5 L16.974919,8.5 L14.974919,8.5 Z M17.974919,4.5 L17.974919,11.5 L21.974919,8 L17.974919,4.5 Z',
          fill: '#4D4F56',
        }),
        h('path', {
          d: 'M9,3 C9.55228475,3 10,3.44771525 10,4 L10,12 C10,12.5522847 9.55228475,13 9,13 L1,13 C0.44771525,13 3.38176876e-17,12.5522847 0,12 L0,4 C-6.76353751e-17,3.44771525 0.44771525,3 1,3 L9,3 Z M4.928,3.892 L4.112,4.116 C4.272,4.46 4.424,4.82 4.552,5.196 L1.696,5.196 L1.696,6.012 L4.576,6.012 L4.576,7.588 L2.088,7.588 L2.088,8.38 L4.576,8.38 L4.576,10.252 L1.424,10.252 L1.424,11.068 L8.584,11.068 L8.584,10.252 L5.424,10.252 L5.424,8.38 L7.92,8.38 L7.92,7.588 L5.424,7.588 L5.424,6.012 L8.312,6.012 L8.312,5.196 L5.368,5.196 C5.264,4.804 5.12,4.372 4.928,3.892 Z',
          fill: '#3A84FF',
        }),
      ]
    ),
  ]
);

/** trace检索table trace视角-状态码(status.code)列 不同类型显示 tag color 配置 */
export const SERVICE_STATUS_COLOR_MAP = {
  error: {
    tagColor: '#ea3536',
    tagBgColor: '#feebea',
  },
  normal: {
    tagColor: '#14a568',
    tagBgColor: '#e4faf0',
  },
};

/** trace检索table trace视角-调用类型(root_service_category)列 */
export const SERVICE_CATEGORY_MAP = {
  http: window.i18n.t('网页'),
  rpc: window.i18n.t('远程调用'),
  db: window.i18n.t('数据库'),
  messaging: window.i18n.t('消息队列'),
  async_backend: window.i18n.t('后台任务'),
  all: window.i18n.t('全部'),
  other: window.i18n.t('其他'),
};

/** trace检索table span视角-类型(kind)列 不同类型显示 prefix-icon 渲染配置 */
export const SPAN_KIND_MAPS: Record<number, GetTableCellRenderValue<ExploreTableColumnTypeEnum.PREFIX_ICON>> = {
  0: { alias: window.i18n.t('未定义'), prefixIcon: 'icon-monitor icon-weizhi span-kind-icon' },
  1: {
    alias: window.i18n.t('内部调用'),
    prefixIcon: () => h(LocalInvokerIcon, { class: 'span-kind-icon' }),
  },
  2: { alias: window.i18n.t('同步被调'), prefixIcon: () => h(SyncCalledIcon, { class: 'span-kind-icon' }) },
  3: { alias: window.i18n.t('同步主调'), prefixIcon: () => h(SyncInvokerIcon, { class: 'span-kind-icon' }) },
  4: { alias: window.i18n.t('异步主调'), prefixIcon: () => h(AsyncInvokerIcon, { class: 'span-kind-icon' }) },
  5: { alias: window.i18n.t('异步被调'), prefixIcon: () => h(AsyncCalledIcon, { class: 'span-kind-icon' }) },
  6: { alias: window.i18n.t('推断'), prefixIcon: 'icon-monitor icon-tuiduan span-kind-icon' },
};

/** trace检索table span视角-状态(status.code)列 不同类型显示 prefix-icon 渲染配置 */
export const SPAN_STATUS_CODE_MAP: Record<number, GetTableCellRenderValue<ExploreTableColumnTypeEnum.PREFIX_ICON>> = {
  0: { alias: window.i18n.t('未设置'), prefixIcon: 'status-code-icon-warning' },
  1: { alias: window.i18n.t('正常'), prefixIcon: 'status-code-icon-normal' },
  2: { alias: window.i18n.t('异常'), prefixIcon: 'status-code-icon-failed' },
};

/**
 * 根据id查找name所对应的字段别名，没有找到返回空字符串
 */
export const transformFieldName = (id: string, name: number | string) => {
  switch (id) {
    case 'kind':
    case 'root_span_kind':
    case 'root_service_kind':
    case 'collections.kind':
      return SPAN_KIND_MAPS[name]?.alias || '';
    case 'root_service_category':
      return SERVICE_CATEGORY_MAP[name] || '';
    case 'status.code':
      return SPAN_STATUS_CODE_MAP[name]?.alias || '';
    default:
      return '';
  }
};
