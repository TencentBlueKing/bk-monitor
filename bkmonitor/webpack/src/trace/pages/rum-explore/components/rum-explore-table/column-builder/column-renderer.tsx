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
  type RumEllipsisModeType,
  EVENTS_FIELD_PREFIX,
  RumModeEnum,
  SESSION_ID_FIELD,
  SPAN_TYPE_FIELD,
  VIEW_URL_FIELD,
} from '../../../constants';
import { ARRAY_ITEM_EMPTY_PLACEHOLDER } from '../../../utils/array-field-formatter';
import ColumnHeader from '../components/column-header/column-header';
import CompositeAction from '../components/composite-cell/composite-action';
import CompositeCell from '../components/composite-cell/composite-cell';
import EventsCell from '../components/events-cell/events-cell';
import FieldValue from '../components/field-value/field-value';
import { getFieldRule } from '../field-rules';
import { hasFieldValue, resolveCompositeRows } from './column-layout';

import type { BaseTableColumn } from '../../../../trace-explore/components/trace-explore-table/typing';
import type { CompositeRow, CompositeValue, IRumField, IRumSpanRecord, RumModeType } from '../../../typings';
import type { RumColumnActions } from '../hooks/use-rum-columns';
import type { resolveColumnLayout } from './column-layout';
import type { SlotReturnValue } from 'tdesign-vue-next';

/**
 * @description 为 CommonTable 创建表头和单元格的渲染回调。
 * @param column 基础列配置
 * @param field 展示列的字段元信息
 * @param layout 已解析的复合布局和分析字段
 * @param mode 当前检索视角
 * @param actions 表格传入的业务交互
 * @param ellipsisMode 单元格文本省略方式
 * @returns 接入共享表格的列渲染属性
 */
export const buildRumColumnRenderer = (
  column: BaseTableColumn,
  field: IRumField | undefined,
  layout: ReturnType<typeof resolveColumnLayout>,
  mode: RumModeType,
  actions: RumColumnActions,
  ellipsisMode: RumEllipsisModeType
): Pick<BaseTableColumn, 'align' | 'cellRenderer' | 'title'> => {
  const fieldName = column.colKey;
  const isSpanName = fieldName === 'span_name';
  const count = !!getFieldRule(fieldName).byMode?.[mode]?.drillDown && !layout.sections;
  return {
    /** 在当前视角识别为计数的独立列右对齐。 */
    align: count ? 'right' : column.align,
    title: () =>
      (
        <ColumnHeader
          class={layout.sections && 'rum-composite-header'}
          analysis={layout.analysisField && { field: layout.analysisField, candidates: layout.analysisFields }}
          colKey={fieldName}
          field={field}
          onFieldAnalysis={actions.onFieldAnalysis}
        />
      ) as unknown as SlotReturnValue,
    /**
     * @description 根据当前记录渲染复合列或普通列，并在对应位置接入关联操作。
     * @param {IRumSpanRecord} row 当前记录
     * @param runtimeColumn CommonTable 传入的运行时列配置
     * @param ctx 表格行标识及单元格省略规则
     * @returns 当前单元格的渲染节点
     */
    cellRenderer: (row: IRumSpanRecord, runtimeColumn, ctx) => {
      const rowId = ctx.getRowId(row);
      if (layout.sections) {
        const rows = resolveCompositeRows(layout.sections, row);
        /** Span 名称和页面 URL 的复合列主行有实际内容时，才承载关联详情入口。 */
        const hasRelatedAnchor =
          (isSpanName || fieldName === VIEW_URL_FIELD) &&
          rows.some(
            section =>
              section.index === 0 &&
              (section.items.some(item => !item.isPlaceholder) || section.badges.some(badge => !badge.isPlaceholder))
          );
        const traceId = hasRelatedAnchor && isSpanName ? getLinkedTraceId(row) : '';
        const rawSessionId = row[SESSION_ID_FIELD];
        const sessionId =
          hasRelatedAnchor && mode !== RumModeEnum.SESSION && typeof rawSessionId === 'string'
            ? rawSessionId.trim()
            : '';
        /**
         * @description 渲染复合列成员，保留主字段占位并按标签位置应用展示配置。
         * @param {CompositeValue} member 当前记录解析出的字段和值
         * @param {'badge' | 'item'} placement 成员在复合行中的位置
         * @returns 当前成员的渲染节点
         */
        const renderMember = (member: CompositeValue, placement: 'badge' | 'item') => {
          if (member.isPlaceholder) return <span class='rum-empty-text'>{ARRAY_ITEM_EMPTY_PLACEHOLDER}</span>;
          return (
            <FieldValue
              context={{
                field: member.field,
                fieldName: member.field.name,
                placement,
                row,
                rowId,
                value: member.value,
              }}
              actions={actions}
              ellipsisMode={ellipsisMode}
              mode={mode}
            />
          );
        };

        return (
          <CompositeCell
            v-slots={{
              item: (item: CompositeValue) => renderMember(item, 'item'),
              badge: (badge: CompositeValue) => renderMember(badge, 'badge'),
              prefix: (section: CompositeRow) =>
                renderUrlAction(section, isSpanName, row[SPAN_TYPE_FIELD], actions.hoverPopoverTools),
              suffix: (section: CompositeRow) =>
                section.index === 0 ? renderRelatedActions(row, sessionId, traceId, actions) : null,
            }}
            data-trace-id={traceId || undefined}
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
          <div class={isSpanName ? 'rum-plain-ellipsis' : ctx.isEnabledCellEllipsis(runtimeColumn)}>
            {hasFieldValue(value) ? (
              <FieldValue
                actions={actions}
                context={{ field, fieldName, placement: 'column', row, rowId, value }}
                ellipsisMode={ellipsisMode}
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

/**
 * @description 从扁平化的 links 字段读取关联 Trace ID，多个 ID 时与时间轴一样取首条。
 * @param {IRumSpanRecord} row 当前列表记录
 * @returns {string} 首条关联 Trace ID，缺失时返回空串
 */
function getLinkedTraceId(row: IRumSpanRecord) {
  const links = row['links.trace_id'];
  const traceId = Array.isArray(links) ? links[0] : links;
  return typeof traceId === 'string' ? traceId.trim() : '';
}

/**
 * @description 复合列主行按会话 ID 展示 Session，按流式检索命中结果展示 Trace。
 * @param {IRumSpanRecord} row 来源行，用于打开会话后的表格高亮
 * @param {string} sessionId 当前行的关联会话 ID
 * @param {string} traceId 用于读取命中结果的关联 Trace ID
 * @param {RumColumnActions} actions 读取命中结果和打开详情的回调
 * @returns 关联详情入口节点，无可用入口时返回 null
 */
function renderRelatedActions(row: IRumSpanRecord, sessionId: string, traceId: string, actions: RumColumnActions) {
  const trace = traceId ? actions.getTraceInfo(traceId) : undefined;
  if (!sessionId && !trace) return null;

  return (
    <span class='rum-composite-actions'>
      {sessionId && (
        <CompositeAction
          hoverPopoverTools={actions.hoverPopoverTools}
          icon='icon-Jump'
          label='Session'
          tooltip={window.i18n.t('查看 Session')}
          onClick={() => actions.onOpenSessionDetail(row, sessionId)}
        />
      )}
      {trace && (
        <CompositeAction
          hoverPopoverTools={actions.hoverPopoverTools}
          icon='icon-Jump'
          label='Trace'
          tooltip={window.i18n.t('查看 Trace')}
          onClick={() => actions.onOpenTraceDetail(trace)}
        />
      )}
    </span>
  );
}

/**
 * @description 为复合行中配置为 link 的 HTTP(S) 地址提供外链入口。
 * @param {CompositeRow} section 已按当前记录解析的复合行
 * @param {boolean} isSpanName 当前列是否为 Span Name
 * @param {string | undefined} spanType 当前记录的 Span 类型
 * @param {RumColumnActions['hoverPopoverTools']} hoverPopoverTools 表格共用的悬浮提示实例
 * @returns 满足显示条件时返回模拟页面入口节点
 */
function renderUrlAction(
  section: CompositeRow,
  isSpanName: boolean,
  spanType: string | undefined,
  hoverPopoverTools: RumColumnActions['hoverPopoverTools']
) {
  if (isSpanName && spanType !== 'view') return null;

  const url = section.items.find(item => item.type === 'link' && !item.isPlaceholder)?.value;
  if (typeof url !== 'string') return null;
  try {
    const { protocol } = new URL(url);
    if (protocol !== 'http:' && protocol !== 'https:') return null;
  } catch {
    return null;
  }

  return (
    <CompositeAction
      hoverPopoverTools={hoverPopoverTools}
      href={url}
      icon='icon-mc-goto'
      tooltip={window.i18n.t('打开模拟页面')}
    />
  );
}
