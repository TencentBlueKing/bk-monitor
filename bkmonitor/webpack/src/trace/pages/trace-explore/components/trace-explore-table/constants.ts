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

import type { GetTableCellRenderValue, ExploreTableColumnTypeEnum } from './typing';

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
  0: { alias: window.i18n.t('未定义'), prefixIcon: 'icon-monitor icon-weizhi' },
  1: { alias: window.i18n.t('内部调用'), prefixIcon: 'icon-monitor icon-neibutiaoyong1' },
  2: { alias: window.i18n.t('同步被调'), prefixIcon: 'icon-monitor icon-tongbubeitiao' },
  3: { alias: window.i18n.t('同步主调'), prefixIcon: 'icon-monitor icon-tongbuzhutiao' },
  4: { alias: window.i18n.t('异步主调'), prefixIcon: 'icon-monitor icon-yibuzhutiao' },
  5: { alias: window.i18n.t('异步被调'), prefixIcon: 'icon-monitor icon-yibubeitiao' },
  6: { alias: window.i18n.t('推断'), prefixIcon: 'icon-monitor icon-tuiduan' },
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
