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
  RUM_DETAIL_SPAN_TYPES,
  RumModeEnum,
  SESSION_ID_FIELD,
  SPAN_TYPE_FIELD,
  VIEW_ID_FIELD,
  VIEW_URL_FIELD,
} from '../../../../constants';
import { hasFieldValue } from '../../column-builder/column-layout';

import type { IRumSpanRecord, RumModeType } from '../../../../typings';
import type { FieldActions } from './field-value';
import type { TippyContent } from 'vue-tippy';

/** 判断字段是否承担 Span 名称的详情和悬浮提示交互。 */
export const isSpanName = (mode: RumModeType, fieldName: string) =>
  mode === RumModeEnum.SPAN && fieldName === 'span_name';

/** 判断当前字段及记录是否具备打开详情的标识。 */
export const canOpenRecordDetail = (mode: RumModeType, fieldName: string, row: IRumSpanRecord, rowId: string) => {
  if (isSpanName(mode, fieldName)) {
    const type = String(row[SPAN_TYPE_FIELD] ?? '');
    return (
      !!rowId &&
      RUM_DETAIL_SPAN_TYPES.has(type) &&
      (type !== RumModeEnum.SESSION || hasFieldValue(row[SESSION_ID_FIELD]))
    );
  }
  if (mode === RumModeEnum.VIEW && fieldName === VIEW_URL_FIELD) return hasFieldValue(row[VIEW_ID_FIELD]);
  return mode === RumModeEnum.SESSION && fieldName === SESSION_ID_FIELD && !!rowId;
};

/**
 * 为 Span 名称生成悬浮事件，提供完整名称与 Span ID。
 * @param row 当前 Span 记录
 * @param label 列标题
 * @param text 已格式化的完整名称
 * @param tools 表格共用的悬浮层控制方法
 */
export const spanNameHover = (
  row: IRumSpanRecord,
  label: string,
  text: string,
  tools: FieldActions['hoverPopoverTools']
) => {
  return {
    onMouseenter: (event: MouseEvent) => {
      tools.showPopover(
        event,
        (
          <div class='span-name-popover-container'>
            <div class='span-name-popover-item'>
              <span class='span-name-popover-item-label'>{label}</span>
              <span class='span-name-popover-item-value'>{text}</span>
            </div>
            <div class='span-name-popover-item'>
              <span class='span-name-popover-item-label'>Span ID</span>
              <span class='span-name-popover-item-value'>{row.span_id || '--'}</span>
            </div>
          </div>
        ) as unknown as TippyContent,
        { theme: 'rum-span-name-popover max-width-40vw text-wrap padding-0' }
      );
    },
    onMouseleave: tools.clearPopoverTimer,
  };
};
