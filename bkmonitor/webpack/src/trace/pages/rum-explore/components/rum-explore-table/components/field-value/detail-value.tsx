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
import { RUM_DETAIL_SPAN_TYPES, RumModeEnum, SESSION_ID_FIELD, SPAN_TYPE_FIELD } from '../../../../constants';
import { hasFieldValue } from '../../column-builder/column-layout';

import type { ValueContext } from '../../../../typings';
import type { TippyContent } from 'vue-tippy';

import './detail-value.scss';

/**
 * @description 检查当前行能否打开 Span 详情，会话类型还需提供会话 ID。
 * @param context 包含当前行和行标识的字段上下文
 * @returns 详情类型受支持且所需标识齐全时返回 true
 */
export function canOpenSpanDetail({ row, rowId }: ValueContext) {
  const type = String(row[SPAN_TYPE_FIELD] ?? '');
  return (
    !!rowId && RUM_DETAIL_SPAN_TYPES.has(type) && (type !== RumModeEnum.SESSION || hasFieldValue(row[SESSION_ID_FIELD]))
  );
}

/**
 * @description 组装同时展示完整名称和 Span ID 的悬浮提示。
 * @param context 包含字段别名和 Span 记录的上下文
 * @param text 格式化后的完整 Span 名称
 * @param t 用于生成默认字段标题的国际化函数
 * @returns 悬浮层所需的提示内容和主题
 */
export function getSpanNameTooltip({ field, row }: ValueContext, text: string, t: (key: string) => string) {
  return {
    theme: 'rum-span-name-popover max-width-40vw text-wrap padding-0',
    content: (
      <div class='span-name-popover-container'>
        <div class='span-name-popover-item'>
          <span class='span-name-popover-item-label'>{field?.alias ?? t('Span 名称')}:</span>
          <span class='span-name-popover-item-value'>{text}</span>
        </div>
        <div class='span-name-popover-item'>
          <span class='span-name-popover-item-label'>Span ID:</span>
          <span class='span-name-popover-item-value'>{row.span_id || '--'}</span>
        </div>
      </div>
    ) as unknown as TippyContent,
  };
}
