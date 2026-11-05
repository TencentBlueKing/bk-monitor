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
 * The above copyright notice and this permission notice shall be included in all copies or substantial portions
 * of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
 * THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
 * CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
 * IN THE SOFTWARE.
 */
import { EMethod } from '../../../../../components/retrieval-filter/typing';
import {
  type BaseTableColumn,
  type TableCellRenderContext,
  ExploreTableColumnTypeEnum,
} from '../../../../trace-explore/components/trace-explore-table/typing';
import { SESSION_COUNT_FIELDS, SESSION_ID_FIELD } from '../../../constants';
import { BaseScenario } from './base-scenario';

import type { IRumCountDrillDown, IRumSpanRecord, RumModeType } from '../../../typings';
import type { SlotReturnValue } from 'tdesign-vue-next';

/**
 * Session 视角数量列配色：View / 动作为主蓝链接，错误为主红加粗下划线
 * （样式见 theme/session-table-theme.scss）。键为 SESSION_COUNT_FIELDS 中的数量列名，
 * 未配置的列回退 'is-blue'。
 */
const SESSION_COUNT_TONE_CLASS: Record<string, string> = {
  action_count: 'is-blue',
  error_count: 'is-danger',
  view_count: 'is-blue',
};

/**
 * @class SessionScenario
 * @classdesc Session 检索场景：会话 ID 链接列、数量统计列（View / 动作 / 错误）的渲染差异在 columnOverrides 中声明；
 *            入口视图 URL 按普通文本展示，其余时间 / 耗时 / 单位列走基类推导。
 *            数量列渲染与下钻参数均在本类内联。
 * @extends BaseScenario
 */
export class SessionScenario extends BaseScenario {
  readonly privateClassName = 'session-table';
  readonly rowKey = SESSION_ID_FIELD;

  protected columnOverrides: Record<string, BaseTableColumn> = {
    /** 会话 ID：按设计稿蓝色链接展示；专属详情未开发前点击由页面占位处理 */
    [SESSION_ID_FIELD]: {
      renderType: ExploreTableColumnTypeEnum.CLICK,
      clickCallback: (row, _column, event) => {
        event.stopPropagation();
        this.context.onOpenDetail(row);
      },
    },
    /** 数量统计列：右对齐，按列配色，点击回传已解析的下钻参数 */
    ...Object.fromEntries(
      Object.keys(SESSION_COUNT_FIELDS).map(field => [
        field,
        {
          align: 'right',
          cellRenderer: (row, column, renderCtx) => this.renderSessionCountCell(row, column, renderCtx),
        },
      ])
    ),
  };

  constructor(
    protected readonly context: {
      /** 点击数量统计列：回传已解析的目标视角与检索条件 */
      onCountClick: (payload: IRumCountDrillDown) => void;
      /** 点击会话 ID：由页面决定打开详情或占位 */
      onOpenDetail: (row: Record<string, unknown>) => void;
    } & BaseScenario['context']
  ) {
    super(context);
  }

  // ----------------- Session 场景私有逻辑方法 -----------------

  /**
   * @description Session 数量列下钻参数：目标视角由列映射决定，条件统一按会话 ID 等值检索。
   *              会话 ID 为空或列不在 SESSION_COUNT_FIELDS 映射中时返回 null，调用方据此跳过跳转。
   * @param {IRumSpanRecord} row 当前行数据，会话 ID 取自 SESSION_ID_FIELD
   * @param {string} colKey 数量列列名，用于查 SESSION_COUNT_FIELDS 得到目标视角
   * @returns {IRumCountDrillDown | null} 下钻参数；不可下钻时为 null
   */
  private resolveSessionCountDrillDown(row: IRumSpanRecord, colKey: string): IRumCountDrillDown | null {
    const sessionId = String(row?.[SESSION_ID_FIELD] ?? '');
    const targetMode: RumModeType | undefined = SESSION_COUNT_FIELDS[colKey];
    if (!sessionId || !targetMode) return null;
    return {
      condition: { key: SESSION_ID_FIELD, method: EMethod.eq, value: sessionId },
      targetMode,
    };
  }

  /**
   * @description Session 数量统计单元格渲染：0 灰色不可点，大于 0 按列配色为可下钻链接。
   *              DOM 层级与普通文本列一致，非有限数值按 0 处理；文本节点复用 CLICK 列选择器以支持右键条件菜单。
   * @param {IRumSpanRecord} row 当前行数据，数量取 row[column.colKey]
   * @param {BaseTableColumn} column 当前列配置，colKey 同时决定取值与配色
   * @param {TableCellRenderContext} renderCtx 列渲染上下文，提供省略类名计算与行 rowId
   * @returns {SlotReturnValue} 单元格渲染节点
   */
  private renderSessionCountCell(
    row: IRumSpanRecord,
    column: BaseTableColumn,
    renderCtx: TableCellRenderContext
  ): SlotReturnValue {
    const value = Number(row?.[column.colKey]);
    const count = Number.isFinite(value) ? value : 0;
    const isLink = Boolean(count);
    const toneClass = SESSION_COUNT_TONE_CLASS[column.colKey] ?? 'is-blue';
    return (
      <div class='explore-col explore-text-col session-count-col'>
        <div class={renderCtx.isEnabledCellEllipsis(column)}>
          <span
            class={`session-count-value explore-col-text explore-click-text ${isLink ? toneClass : 'is-zero'}`}
            data-col-id={column.colKey}
            data-row-id={renderCtx.getRowId(row)}
            onClick={
              isLink
                ? (e: MouseEvent) => {
                    e.stopPropagation();
                    const payload = this.resolveSessionCountDrillDown(row, column.colKey);
                    if (payload) this.context.onCountClick(payload);
                  }
                : undefined
            }
          >
            {count}
          </span>
        </div>
      </div>
    ) as unknown as SlotReturnValue;
  }
}
