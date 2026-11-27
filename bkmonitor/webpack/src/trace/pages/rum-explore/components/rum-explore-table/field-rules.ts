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
import {
  RUM_OUTCOME_TYPE_MAP,
  RUM_VIEW_LOADING_TYPE_ICONS,
  RumModeEnum,
  SESSION_ID_FIELD,
  SPAN_TYPE_FIELD,
  VIEW_ID_FIELD,
  VIEW_URL_FIELD,
} from '../../constants';
import { hasFieldValue } from './column-builder/column-layout';
import { canOpenSpanDetail, getSpanNameTooltip } from './components/field-value/detail-value';
import { httpStatusAppearance, kindAppearance, spanTypeAppearance, statusAppearance } from './field-appearance';

import type { FieldRule } from '../../typings';

/** 页面视角下共用的计数规则，按页面 ID 下钻到 Span 视角。 */
const viewCount = { drillDown: { idField: VIEW_ID_FIELD, targetMode: RumModeEnum.SPAN } };

/** 按真实字段名登记列表中的特殊展示与交互，未登记的字段走接口元数据。 */
const fieldRules: Readonly<Record<string, FieldRule>> = {
  /** Span 名称的悬浮提示和详情资格分别判定。 */
  span_name: {
    byMode: { [RumModeEnum.SPAN]: { canOpenDetail: canOpenSpanDetail, getTooltip: getSpanNameTooltip } },
  },
  /** 会话视角中有行标识的会话 ID 可打开详情。 */
  [SESSION_ID_FIELD]: { byMode: { [RumModeEnum.SESSION]: { canOpenDetail: ({ rowId }) => !!rowId } } },
  /** 页面视角中通过页面 ID 判定 URL 字段能否打开详情。 */
  [VIEW_URL_FIELD]: {
    byMode: { [RumModeEnum.VIEW]: { canOpenDetail: ({ row }) => hasFieldValue(row[VIEW_ID_FIELD]) } },
  },
  [SPAN_TYPE_FIELD]: { appearance: spanTypeAppearance },
  kind: { appearance: kindAppearance },
  'attributes.outcome.type': {
    /**
     * @description 为结果类型提供图标、图标样式和备用文案。
     * @param value 原始结果类型
     * @returns 字段展示配置
     */
    appearance(value) {
      const meta = RUM_OUTCOME_TYPE_MAP[String(value)];
      return {
        text: meta?.label,
        icon: meta?.icon ? { icon: meta.icon, className: `prefix-icon ${meta.className}` } : undefined,
      };
    },
  },
  'attributes.resource.cache.hit': {
    /**
     * @description 处理接口返回的布尔值或字符串形式的缓存命中标记。
     * @param value 原始缓存命中值
     * @returns 命中时提供勾选图标和备用文案，其余值返回空对象
     */
    appearance: value =>
      value === true || value === 'true' ? { text: 'HIT', icon: { icon: 'icon-mc-check-small' } } : {},
  },
  'status.code': { appearance: statusAppearance, columnAsTag: true },
  'attributes.http.response.status_code': { appearance: httpStatusAppearance, columnAsTag: true },
  'attributes.http.request.method': { columnAsTag: true },
  'attributes.action.frustration.type': { badge: { className: 'rum-badge-long-task' } },
  'attributes.action.type': { badge: { className: 'rum-badge-action' } },
  'attributes.long_task.entry_type': { badge: { className: 'rum-badge-long-task' } },
  'attributes.resource.type': { badge: { className: 'rum-badge-resource' } },
  'attributes.view.loading_type': {
    badge: {
      className: 'rum-badge-view',
      /**
       * @description 按页面加载类型选择复合标签图标。
       * @param value 单个标签对应的原始加载类型
       * @returns 已登记的图标配置，未知类型返回 undefined
       */
      resolveIcon(value) {
        const type = String(value) as keyof typeof RUM_VIEW_LOADING_TYPE_ICONS;
        if (Object.hasOwn(RUM_VIEW_LOADING_TYPE_ICONS, type)) return { icon: RUM_VIEW_LOADING_TYPE_ICONS[type] };
      },
    },
  },
  'events.attributes.exception.type': { badge: { className: 'rum-badge-error' } },
  /** 视口尺寸在复合标签中使用固定图标。 */
  'virtual.viewport': { badge: { resolveIcon: () => ({ icon: 'icon-chuangkou', className: 'is-viewport' }) } },
  'attributes.view.url': { itemTextClass: 'rum-field-full-url' },
  'attributes.url.full': { itemTextClass: 'rum-field-full-url' },
  action_count: {
    byMode: {
      [RumModeEnum.SESSION]: {
        drillDown: { idField: SESSION_ID_FIELD, targetMode: RumModeEnum.SPAN, spanType: 'action' },
      },
      [RumModeEnum.VIEW]: viewCount,
    },
  },
  error_count: {
    byMode: {
      [RumModeEnum.SESSION]: {
        drillDown: { idField: SESSION_ID_FIELD, targetMode: RumModeEnum.SPAN, spanType: 'error' },
      },
      [RumModeEnum.VIEW]: viewCount,
    },
  },
  view_count: {
    byMode: { [RumModeEnum.SESSION]: { drillDown: { idField: SESSION_ID_FIELD, targetMode: RumModeEnum.VIEW } } },
  },
  request_count: { byMode: { [RumModeEnum.VIEW]: viewCount } },
};

/** 普通字段沿用通用渲染和接口元数据。 */
const defaultRule: FieldRule = {};

/**
 * @description 查找字段登记的展示和交互规则。
 * @param fieldName 列或复合成员对应的真实字段名
 * @returns 字段专用规则，未登记时返回默认规则
 */
export function getFieldRule(fieldName: string): FieldRule {
  return Object.hasOwn(fieldRules, fieldName) ? fieldRules[fieldName] : defaultRule;
}
