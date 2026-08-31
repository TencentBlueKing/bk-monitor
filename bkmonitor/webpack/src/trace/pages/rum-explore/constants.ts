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

import { hexToRgba } from 'monitor-common/utils/colorHelpers';

import ActionIcon from '../../static/img/rum-explore/span-type/action.svg';
import CustomIcon from '../../static/img/rum-explore/span-type/custom.svg';
import ErrorIcon from '../../static/img/rum-explore/span-type/error.svg';
import LongTaskIcon from '../../static/img/rum-explore/span-type/long-task.svg';
import ResourceIcon from '../../static/img/rum-explore/span-type/resource.svg';
import ViewIcon from '../../static/img/rum-explore/span-type/view.svg';
import VitalIcon from '../../static/img/rum-explore/span-type/vital.svg';
import WebsocketIcon from '../../static/img/rum-explore/span-type/websocket.svg';

import type { RumMode } from './typings';

/** 字段展示类型（仅特殊渲染的字段才返回此字段，取值需与 view_config 接口对齐） */
export const RumFieldDisplayEnum = {
  /** 日期时间字段，按时间列渲染 */
  DATETIME: 'datetime',
  /** 耗时字段，按 duration 列渲染 */
  DURATION: 'duration',
} as const;

/**
 * HTTP 状态码分组，取值即状态码的百位数字，可直接由 Math.floor(code / 100) 查得。
 */
export const RumHttpStatusCodeGroupEnum = {
  /** 2xx 成功 */
  SUCCESS: 2,
  /** 3xx 重定向 */
  REDIRECT: 3,
  /** 4xx 客户端错误 */
  CLIENT_ERROR: 4,
  /** 5xx 服务端错误 */
  SERVER_ERROR: 5,
} as const;

/** 「类型选择」中代表不限类型的值，非后端枚举 */
export const ALL_SPAN_TYPE = '';

/** span 类型对应的字段名，快捷筛选与按类型切列都基于它 */
export const SPAN_TYPE_FIELD = 'attributes.span_type';

/** 表格滚动加载每页条数 */
export const RUM_TABLE_PAGE_LIMIT = 30;

/** 维度统计面板 TopK 展示条数，超出走「更多」抽屉 */
export const RUM_TOPK_LIMIT = 5;

interface ISpanTypeMeta {
  /** 类型图标，取自设计稿导出的 svg 资源，颜色已内置在 svg 中 */
  icon: string;
  label: string;
}

/**
 * span 类型的展示元数据。
 *
 * 类型列表本身由 view_config 接口的 span_type_display_fields 驱动，这里只负责图标与文案；
 * 接口新增类型时未命中的走 attributes.span_type 的 option_values 别名兜底，不影响功能。
 */
export const SPAN_TYPE_META: Record<string, ISpanTypeMeta> = {
  view: { icon: ViewIcon, label: 'View' },
  resource: { icon: ResourceIcon, label: 'Resource' },
  error: { icon: ErrorIcon, label: 'Error' },
  vital: { icon: VitalIcon, label: 'Vital' },
  long_task: { icon: LongTaskIcon, label: 'Long task' },
  action: { icon: ActionIcon, label: 'Action' },
  websocket: { icon: WebsocketIcon, label: 'Websocket' },
  custom: { icon: CustomIcon, label: 'Custom' },
};

/**
 * 字段分组的图标。
 *
 * 分组由接口返回，这里按分组标识做展示层映射，未命中时用默认图标，不阻塞渲染。
 */
export const RUM_FIELD_GROUP_ICON_MAP: Record<string, string> = {
  COMMON: 'icon-gonggongziduan',
  APPLICATION: 'icon-yingyongbanben',
  DEVICE_BROWSER: 'icon-zhongduan',
  NETWORK: 'icon-web1',
  USER: 'icon-user2',
  RESOURCE: 'icon-Resource',
  VIEW: 'icon-View',
  ACTION: 'icon-Action',
  WEB_VITALS: 'icon-a-WebVital',
};

export const DEFAULT_FIELD_GROUP_ICON = 'icon-mc-list';

/** 「原始字段」分组的标识，该分组由前端按 is_real 聚合而来，不来自接口 */
export const RAW_FIELD_GROUP_NAME = '__raw_fields__';

export const RAW_FIELD_GROUP_ICON = 'icon-yuanshiziduan';

/** 微秒级时间戳字段，按日期时间展示而非耗时 */
export const RUM_TIME_FIELDS = new Set(['start_time', 'end_time', 'events.timestamp']);

/** 以蓝色链接样式展示、点击可加为检索条件的字段 */
export const RUM_LINK_FIELDS = new Set(['span_name', 'attributes.view.url_template']);

/** 支持排序的字段类型 */
export const RUM_SORTABLE_FIELD_TYPES = new Set(['date', 'double', 'integer', 'long']);

/** 列宽，未列出的字段使用 DEFAULT_COLUMN_WIDTH */
export const RUM_COLUMN_WIDTH_MAP: Record<string, number> = {
  span_name: 225,
  'attributes.span_type': 146,
  end_time: 172,
  start_time: 172,
  elapsed_time: 140,
  'status.code': 120,
  'attributes.view.url_template': 172,
  'resource.user_agent.name': 137,
  'attributes.user.id': 133,
};

export const DEFAULT_COLUMN_WIDTH = 150;

/** 表格列最小宽度 */
export const DEFAULT_MIN_COLUMN_WIDTH = 100;

/** status.code 列的展示配置 */
export const RUM_STATUS_CODE_MAP = {
  0: {
    alias: window.i18n.t('未设置'),
    tagBgColor: '#FFF3E1',
    tagColor: '#FF9C01',
    tagHoverBgColor: hexToRgba('#FFF3E1', 0.8),
    tagHoverColor: hexToRgba('#FF9C01', 0.8),
  },
  1: {
    alias: window.i18n.t('正常'),
    tagBgColor: '#E6F9EB',
    tagColor: '#2DCB56',
    tagHoverBgColor: hexToRgba('#E6F9EB', 0.8),
    tagHoverColor: hexToRgba('#2DCB56', 0.8),
  },
  2: {
    alias: window.i18n.t('异常'),
    tagBgColor: '#FDE7E7',
    tagColor: '#EA3636',
    tagHoverBgColor: hexToRgba('#FDE7E7', 0.8),
    tagHoverColor: hexToRgba('#EA3636', 0.8),
  },
};

/** attributes.http.response.status_code 列按状态码分组的展示配置 */
export const RUM_HTTP_STATUS_CODE_MAP: Record<
  number,
  { tagBgColor: string; tagColor: string; tagHoverBgColor: string; tagHoverColor: string }
> = {
  [RumHttpStatusCodeGroupEnum.SUCCESS]: {
    tagBgColor: '#21A380',
    tagColor: '#FFFFFF',
    tagHoverBgColor: hexToRgba('#21A380', 0.8),
    tagHoverColor: hexToRgba('#FFFFFF', 0.8),
  },
  [RumHttpStatusCodeGroupEnum.REDIRECT]: {
    tagBgColor: '#3A84FF',
    tagColor: '#FFFFFF',
    tagHoverBgColor: hexToRgba('#3A84FF', 0.8),
    tagHoverColor: hexToRgba('#FFFFFF', 0.8),
  },
  [RumHttpStatusCodeGroupEnum.CLIENT_ERROR]: {
    tagBgColor: '#F59500',
    tagColor: '#FFFFFF',
    tagHoverBgColor: hexToRgba('#F59500', 0.8),
    tagHoverColor: hexToRgba('#FFFFFF', 0.8),
  },
  [RumHttpStatusCodeGroupEnum.SERVER_ERROR]: {
    tagBgColor: '#EA3636',
    tagColor: '#FFFFFF',
    tagHoverBgColor: hexToRgba('#EA3636', 0.8),
    tagHoverColor: hexToRgba('#FFFFFF', 0.8),
  },
};

/** 视角 Tab 配置，当前仅 span 有实现，其余渲染占位 */
export const RUM_MODE_TAB_LIST: Array<{ disabled: boolean; icon: string; label: string; value: RumMode }> = [
  { value: 'session', label: 'Session', icon: 'icon-Session', disabled: true },
  { value: 'view', label: 'View', icon: 'icon-View', disabled: true },
  { value: 'span', label: 'Span (OT)', icon: 'icon-Span', disabled: false },
];

/** 常驻筛选设置在用户配置中的 key 前缀 */
export const RUM_RESIDENT_SETTING_KEY = 'RUM_EXPLORE_RESIDENT_SETTING';

/** 列配置（显隐/顺序 + 列宽）在用户配置中的 key */
export const RUM_COLUMN_CONFIG_KEY = 'RUM_EXPLORE_COLUMN_CONFIG';

/** 收藏类型标识，需与后端 favorite type 对齐 */
export const RUM_FAVORITE_TYPE = 'rum';

/** 视图根节点 class，同时作为表格滚动容器选择器（.${RUM_EXPLORE_VIEW_CLASS}） */
export const RUM_EXPLORE_VIEW_CLASS = 'rum-explore-view';
