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
import { EVENTS_FIELD_PREFIX, RumModeEnum, SESSION_ID_FIELD, SPAN_TYPE_FIELD, VIEW_URL_FIELD } from '../../../constants';
import { ARRAY_ITEM_EMPTY_PLACEHOLDER } from '../../../utils/array-field-formatter';
import ColumnHeader from '../components/column-header/column-header';
import ActionPlaceholder from '../components/composite-cell/action-placeholder';
import CompositeCell from '../components/composite-cell/composite-cell';
import EventsCell from '../components/events-cell/events-cell';
import { resolveCountField } from '../components/field-value/count-value';
import FieldValue from '../components/field-value/field-value';
import { hasFieldValue, resolveCompositeRows } from './column-layout';

import type { BaseTableColumn } from '../../../../trace-explore/components/trace-explore-table/typing';
import type { IRumField, IRumSpanRecord, RumModeType } from '../../../typings';
import type { RumColumnActions } from '../hooks/use-rum-columns';
import type { CompositeRow, CompositeValue, resolveColumnLayout } from './column-layout';
import type { SlotReturnValue } from 'tdesign-vue-next';

/**
 * 为 CommonTable 创建表头和单元格的渲染回调。
 * @param column 基础列配置
 * @param field 展示列的字段元信息
 * @param layout 已解析的复合布局和分析字段
 * @param mode 当前检索视角
 * @param actions 表格传入的业务交互
 * @returns 接入共享表格的列渲染属性
 */
export const buildRumColumnRenderer = (
  column: BaseTableColumn,
  field: IRumField | undefined,
  layout: ReturnType<typeof resolveColumnLayout>,
  mode: RumModeType,
  actions: RumColumnActions
): Pick<BaseTableColumn, 'align' | 'cellRenderer' | 'title'> => {
  const fieldName = column.colKey;
  const count = !!resolveCountField(mode, fieldName) && !layout.sections;
  return {
    align: count ? 'right' : column.align,
    title: () =>
      (
        <ColumnHeader
          analysis={layout.analysisField && { field: layout.analysisField, candidates: layout.analysisFields }}
          colKey={fieldName}
          field={field}
          onFieldAnalysis={actions.onFieldAnalysis}
        />
      ) as unknown as SlotReturnValue,
    cellRenderer: (row: IRumSpanRecord, runtimeColumn, ctx) => {
      const rowId = ctx.getRowId(row);
      if (layout.sections) {
        const rows = resolveCompositeRows(layout.sections, row);
        /** 将复合成员的原始值及其位置交给共用字段组件。 */
        const renderMember = (member: CompositeValue, placement: 'badge' | 'item') => (
          <FieldValue
            actions={actions}
            context={{ field: member.field, fieldName: member.field.name, placement, row, rowId, value: member.value }}
            mode={mode}
          />
        );

        return (
          <CompositeCell
            v-slots={{
              item: (item: CompositeValue) => renderMember(item, 'item'),
              badge: (badge: CompositeValue) => renderMember(badge, 'badge'),
              prefix: renderUrlPlaceholder,
              suffix: (section: CompositeRow) => renderRelatedPlaceholders(section, fieldName, mode, row),
            }}
            rows={rows}
          />
        ) as unknown as SlotReturnValue;
      }
      if (mode === RumModeEnum.SPAN && fieldName.startsWith(EVENTS_FIELD_PREFIX)) {
        return (
          <EventsCell
            active={actions.isActive(rowId, fieldName)}
            column={runtimeColumn}
            ctx={ctx}
            field={field}
            row={row}
            onOpen={() => actions.onEventsCellClick(row, fieldName)}
          />
        ) as unknown as SlotReturnValue;
      }

      const value = row[fieldName];
      return (
        <div class={['explore-col explore-text-col', { 'is-align-right': count }]}>
          <div class={fieldName === 'span_name' ? 'rum-plain-ellipsis' : ctx.isEnabledCellEllipsis(runtimeColumn)}>
            {hasFieldValue(value) ? (
              <FieldValue
                actions={actions}
                context={{ field, fieldName, placement: 'column', row, rowId, value }}
                mode={mode}
              />
            ) : (
              <span class='rum-empty-text'>{ARRAY_ITEM_EMPTY_PLACEHOLDER}</span>
            )}
          </div>
        </div>
      ) as unknown as SlotReturnValue;
    },
  };
};

/** 在存在关联记录时，为复合首行预留对应的入口。 */
const renderRelatedPlaceholders = (
  section: CompositeRow,
  fieldName: string,
  mode: RumModeType,
  row: IRumSpanRecord
) => {
  if (section.index !== 0 || (fieldName !== 'span_name' && fieldName !== VIEW_URL_FIELD)) return null;
  const showSession = mode !== RumModeEnum.SESSION && hasFieldValue(row[SESSION_ID_FIELD]);
  const showTrace = fieldName === 'span_name' && row[SPAN_TYPE_FIELD] === 'resource' && hasFieldValue(row.trace_id);
  if (!showSession && !showTrace) return null;

  return (
    <span class='rum-composite-actions'>
      {showSession && (
        <ActionPlaceholder
          icon='icon-mc-goto'
          label='Session'
        />
      )}
      {showTrace && (
        <ActionPlaceholder
          icon='icon-mc-goto'
          label='Trace'
        />
      )}
    </span>
  );
};

/** 为包含完整 URL 的复合行保留外链图标。 */
const renderUrlPlaceholder = (section: CompositeRow) => {
  if (
    !section.items.some(item => item.field.name === 'attributes.view.url' || item.field.name === 'attributes.url.full')
  ) {
    return null;
  }
  return (
    <ActionPlaceholder
      icon='icon-fenxiang'
      label={window.i18n.t('页面 URL')}
      showLabel={false}
    />
  );
};
