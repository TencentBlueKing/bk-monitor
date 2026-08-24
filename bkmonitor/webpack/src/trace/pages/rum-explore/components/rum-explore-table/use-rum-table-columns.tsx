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
import { computed } from 'vue';
import type { Ref } from 'vue';

import dayjs from 'dayjs';

import { formatDuration } from '../../../../components/trace-view/utils/date';
import FieldTypeIcon from '../../../trace-explore/components/field-type-icon';
import {
  DEFAULT_COLUMN_WIDTH,
  DURATION_COLOR_THRESHOLDS,
  RUM_COLUMN_WIDTH_MAP,
  RUM_LINK_FIELDS,
  RUM_SORTABLE_FIELD_TYPES,
  RUM_STATUS_CODE_MAP,
  RUM_TIME_FIELDS,
  SPAN_TYPE_FIELD,
  SPAN_TYPE_META,
} from '../../constants';

import type { IRumField, IRumSpanRecord } from '../../typings';

interface IUseRumTableColumnsOptions {
  /** 当前展示的列，顺序即列顺序 */
  displayFields: Ref<string[]>;
  fieldMap: Ref<Map<string, IRumField>>;
  /** 点击链接类单元格，把值加为检索条件 */
  onCellFilter: (field: IRumField, value: string) => void;
  /** 点击列头的统计图标 */
  onFieldAnalysis: (trigger: Element, field: IRumField) => void;
}

export function useRumTableColumns(options: IUseRumTableColumnsOptions) {
  function renderCellContent(field: IRumField, row: IRumSpanRecord) {
    const value = row[field.name];
    if (value === undefined || value === null || value === '') {
      return <span class='cell-empty'>--</span>;
    }

    if (field.name === SPAN_TYPE_FIELD) {
      const meta = SPAN_TYPE_META[value as string];
      return (
        <span class='cell-span-type'>
          {meta?.icon && (
            <img
              class='span-type-icon'
              alt=''
              src={meta.icon}
            />
          )}
          <span>{meta?.label || value}</span>
        </span>
      );
    }

    if (field.name === 'status.code') {
      const status = RUM_STATUS_CODE_MAP[Number(value)];
      if (!status) return <span class='cell-empty'>--</span>;
      return (
        <span class={['cell-status', `is-${status.theme}`]}>
          <i class='status-dot' />
          <span>{status.alias}</span>
        </span>
      );
    }

    if (RUM_TIME_FIELDS.has(field.name)) {
      return <span>{dayjs(Math.floor(Number(value) / 1000)).format('YYYY-MM-DD HH:mm:ss')}</span>;
    }

    if (field.field_unit === 'us') {
      const microseconds = Number(value);
      return (
        <span class={['cell-duration', `is-${getDurationTheme(microseconds)}`]}>{formatDuration(microseconds)}</span>
      );
    }

    if (RUM_LINK_FIELDS.has(field.name)) {
      return (
        <span
          class='cell-link'
          v-overflow-tips
          onClick={() => options.onCellFilter(field, `${value}`)}
        >
          {value as string}
        </span>
      );
    }

    return <span v-overflow-tips>{`${value}`}</span>;
  }

  function renderHeader(field: IRumField) {
    return () => (
      <div class='rum-table-header-cell'>
        <FieldTypeIcon type={field.type} />
        <span
          class='header-title'
          v-overflow-tips
        >
          {field.alias}
        </span>
        {field.is_dimensions && (
          <i
            class='icon-monitor icon-Chart header-analysis-icon'
            onClick={event => {
              event.stopPropagation();
              options.onFieldAnalysis(event.currentTarget as Element, field);
            }}
          />
        )}
      </div>
    );
  }

  const columns = computed(() =>
    options.displayFields.value
      .map(name => options.fieldMap.value.get(name))
      .filter(Boolean)
      .map(field => ({
        colKey: field.name,
        title: renderHeader(field),
        width: RUM_COLUMN_WIDTH_MAP[field.name] || DEFAULT_COLUMN_WIDTH,
        minWidth: 100,
        ellipsis: false,
        resizable: true,
        sorter: RUM_SORTABLE_FIELD_TYPES.has(field.type),
        cell: (_h: unknown, cellParams: { row: IRumSpanRecord }) => (
          <div class='rum-table-cell'>{renderCellContent(field, cellParams.row)}</div>
        ),
      }))
  );

  return { columns };
}

/** 耗时按阈值着色，阈值定义见 constants */
function getDurationTheme(microseconds: number) {
  if (microseconds >= DURATION_COLOR_THRESHOLDS.warning) return 'failed';
  if (microseconds >= DURATION_COLOR_THRESHOLDS.normal) return 'warning';
  return 'normal';
}
