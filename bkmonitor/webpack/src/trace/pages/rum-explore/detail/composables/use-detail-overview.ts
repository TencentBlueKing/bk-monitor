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
import { computed, unref } from 'vue';
import type { MaybeRef } from 'vue';

import { SPAN_TYPE_META } from '../../constants';
import { formatUnitValue } from '../../utils';
import {
  BADGE_COLOR,
  DURATION_BADGE_FIELDS,
  OUTCOME_BADGE_COLOR,
  OVERVIEW_ITEM_LABEL_MAP,
  OVERVIEW_ITEMS_PER_ROW,
  OVERVIEW_LINK_FIELDS,
  RATING_FALLBACK_META,
  RATING_META,
  TYPE_BADGE_FIELDS,
} from '../constants';

import type { IRumBadgeVM, IRumDetailHeaderVM, IRumDetailItem, IRumRecordDetail } from '../typings';

/** HTTP 状态码徽标按百位分组着色，与表格状态码列语义一致 */
const HTTP_STATUS_BADGE_COLOR: Record<number, string> = {
  2: '#21A380',
  3: '#3A84FF',
  4: '#F59500',
  5: '#EA3636',
};

/**
 * @description 标题区视图模型：把 overview 的 badges / items 翻译成可直接渲染的结构
 *
 * badges 的配色规则按字段语义分派（耗时 / 类型 / HTTP 状态码 / 结果状态 / 评级），
 * 新增徽标字段时在 constants 的字段集合里登记即可。
 * @param detail 接口返回的详情
 * @param spanType 当前 span 类型，决定左侧 LOGO 图标
 * @param formatField 字段格式化函数，来自 useDetailFormatter
 */
export function useDetailOverview(
  detail: MaybeRef<IRumRecordDetail | null>,
  spanType: MaybeRef<string>,
  formatField: (fieldName: string, value: unknown) => string
) {
  /** 单个 badge 的配色与文案推导 */
  function resolveBadge(badge: IRumDetailItem): IRumBadgeVM {
    const { field_name: fieldName, value } = badge;
    if (DURATION_BADGE_FIELDS.has(fieldName)) {
      /** 耗时字段以微秒存储，vital 指标值以毫秒存储 */
      const unit = fieldName === 'attributes.vital.value' ? 'ms' : 'us';
      return {
        key: fieldName,
        text: badge.alias || formatUnitValue(value, unit),
        icon: 'icon-monitor icon-mc-time',
        ...BADGE_COLOR.duration,
      };
    }
    if (TYPE_BADGE_FIELDS.has(fieldName)) {
      return { key: fieldName, text: badge.alias || String(value ?? ''), ...BADGE_COLOR.type };
    }
    if (fieldName === 'attributes.http.response.status_code') {
      const bgColor = HTTP_STATUS_BADGE_COLOR[Math.floor(Number(value) / 100)] || BADGE_COLOR.default.bgColor;
      return { key: fieldName, text: String(value ?? ''), bgColor, color: '#FFFFFF' };
    }
    if (fieldName === 'attributes.outcome.type') {
      const color = OUTCOME_BADGE_COLOR[String(value)] || BADGE_COLOR.default;
      return { key: fieldName, text: badge.alias || formatField(fieldName, value) || String(value ?? ''), ...color };
    }
    if (fieldName === 'display.rating_level') {
      const meta = RATING_META[String(value)] || RATING_FALLBACK_META;
      return { key: fieldName, text: badge.alias || meta.alias, bgColor: meta.barColor, color: '#FFFFFF' };
    }
    return { key: fieldName, text: badge.alias || String(value ?? ''), ...BADGE_COLOR.default };
  }

  const headerVM = computed<IRumDetailHeaderVM | null>(() => {
    const data = unref(detail);
    if (!data) return null;
    const { overview } = data;
    const items = (overview.items || []).map(item => ({
      key: item.field_name,
      label: item.field_alias || OVERVIEW_ITEM_LABEL_MAP[item.field_name] || item.field_name,
      value: item.alias ?? formatField(item.field_name, item.value),
      isLink: OVERVIEW_LINK_FIELDS.has(item.field_name),
    }));
    return {
      title: overview.title || '',
      logo: SPAN_TYPE_META[unref(spanType)]?.icon || '',
      badges: (overview.badges || []).map(resolveBadge),
      itemRows: chunk(items, OVERVIEW_ITEMS_PER_ROW),
    };
  });

  return { headerVM };
}

/** 把一维数组按固定列数切成多行 */
function chunk<T>(list: T[], size: number): T[][] {
  const rows: T[][] = [];
  for (let i = 0; i < list.length; i += size) {
    rows.push(list.slice(i, i + size));
  }
  return rows;
}
