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
import { get } from '@vueuse/core';

import { formatDuration } from '../../../../../components/trace-view/utils/date';
import { ENABLED_TABLE_CONDITION_MENU_CLASS_NAME } from '../../../../trace-explore/components/trace-explore-table/constants';
import {
  type BaseTableColumn,
  type TableCellRenderContext,
  ExploreTableColumnTypeEnum,
} from '../../../../trace-explore/components/trace-explore-table/typing';
import { RumRatingEnum, VIEW_COUNT_FIELDS, VIEW_ID_FIELD, VIEW_URL_FIELD } from '../../../constants';
import { BaseScenario } from './base-scenario';

import type { IRumFieldRatingConfig, IRumSpanRecord } from '../../../typings';
import type { SlotReturnValue } from 'tdesign-vue-next';

/** 后端 rating_config[].rating → 列表评级样式类（协议值统一取共享层 RumRatingEnum） */
const RATING_CLASS_MAP: Record<string, string> = {
  [RumRatingEnum.GOOD]: 'is-good',
  [RumRatingEnum.NEEDS_IMPROVEMENT]: 'is-needs-improvement',
  [RumRatingEnum.POOR]: 'is-poor',
};

/**
 * @class ViewScenario
 * @classdesc View 检索场景：页面 URL 链接列、Web Vitals 按阈值着色列、数量统计列（错误 / API 请求 / 动作）的渲染差异
 *            在 columnOverrides 中声明；开始时间、页面加载类型（后台枚举别名）等通用渲染走基类推导。
 * @extends BaseScenario
 */
export class ViewScenario extends BaseScenario {
  readonly privateClassName = 'view-table';
  readonly rowKey = VIEW_ID_FIELD;

  protected columnOverrides: Record<string, BaseTableColumn> = {
    /**
     * 页面 URL 列：复用内置 CLICK 渲染（蓝色链接、空值回落 TEXT、右键条件菜单）。
     * 保留溢出 tip 委托类，长 URL hover 可查看完整文本；clickCallback 阻止冒泡，
     * 避免表格行高亮 toggle 把当前详情行的高亮取消。
     */
    [VIEW_URL_FIELD]: {
      renderType: ExploreTableColumnTypeEnum.CLICK,
      clickCallback: (row, _column, event) => {
        event.stopPropagation();
        this.context.onOpenDetail(row);
      },
    },
    /** 数量统计列（错误 / API 请求 / 动作数量）：右对齐，点击切到 Span 视角检索该页面 */
    ...Object.fromEntries(
      [...VIEW_COUNT_FIELDS].map(field => [
        field,
        {
          align: 'right',
          cellRenderer: (row, column, renderCtx) => this.renderCountCell(row, column, renderCtx),
        },
      ])
    ),
  };

  constructor(
    protected readonly context: {
      /** 点击页面 URL：打开该行的详情抽屉 */
      onOpenDetail: (row: Record<string, unknown>) => void;
      /** 点击数量统计列：切到 Span 视角并按该行页面 ID 检索 */
      onViewCountClick: (row: IRumSpanRecord, colKey: string) => void;
    } & BaseScenario['context']
  ) {
    super(context);
  }

  // ----------------- View 场景私有逻辑方法 -----------------

  /**
   * @description 字段元数据推导：带 rating_config 的字段（Web Vitals）按接口下发的阈值着色。
   *              指标名与阈值均不硬编码，后端新增指标或调整阈值时前端无需改动；
   *              未下发 rating_config 的字段回落基类的时间 / 耗时 / 单位格式化。
   *              view_config 刷新会重建列配置，这里捕获的阈值随之更新。
   * @param {string} colKey 列键
   * @returns 声明式列配置
   */
  protected buildBaseline(colKey: string): Partial<BaseTableColumn> {
    const configs = get(this.context.fieldMap).get(colKey)?.rating_config;
    if (configs?.length) {
      return {
        cellRenderer: (row, column, renderCtx) => this.renderRatingCell(row, column, renderCtx, configs),
      };
    }
    return super.buildBaseline(colKey);
  }

  /**
   * @description 评级字段单元格渲染：数值按字段单位格式化（毫秒耗时 / 无量纲分数原样），
   *              按 view_config 下发的 rating_config 命中评级着色（配色见 theme/view-table-theme.scss）
   * @param {IRumSpanRecord} row 当前行数据
   * @param {BaseTableColumn} column 当前列配置项
   * @param {TableCellRenderContext} renderCtx 列渲染上下文
   * @param {IRumFieldRatingConfig[]} configs 该字段的评级阈值配置
   * @returns {SlotReturnValue} 渲染dom
   */
  private renderRatingCell(
    row: IRumSpanRecord,
    column: BaseTableColumn,
    renderCtx: TableCellRenderContext,
    configs: IRumFieldRatingConfig[]
  ) {
    const value = row?.[column.colKey];
    /** 空值与不可转数值的脏数据都交给内置 TEXT 渲染，避免着色的空值单元格与正常空占位符形态不一致 */
    if (value === null || value === undefined || value === '' || !Number.isFinite(Number(value))) {
      return renderCtx.cellRenderHandleMap[ExploreTableColumnTypeEnum.TEXT]?.(row, column, renderCtx);
    }
    const num = Number(value);
    /** 单位为空的指标（CLS）是 0~1 的无量纲分数，原样展示，不能拼时间单位 */
    const unit = get(this.context.fieldMap).get(column.colKey)?.field_unit;
    const text = unit ? formatDuration(num, '', 2, 'ms') : String(value);
    /**
     * DOM 与内置 TEXT 列渲染器（textColumnFormatter）保持一致：explore-col 容器 + 省略容器 + explore-col-text 文本节点，
     * 使单元格内边距、垂直居中、溢出提示与后续插槽的表现和其他列相同；列未配置 suffixSlot，故不渲染后置插槽。
     * 文本节点上挂条件菜单委托类名与 data 属性：左键可弹出「复制 / 添加到本次检索 / 排除 / 新建检索」菜单，
     * 回源取值走 useExploreDataCache，条件值取行内原始数值而非格式化后的展示文本。
     */
    return (
      <div class='explore-col explore-text-col view-vital-col'>
        <div class={renderCtx.isEnabledCellEllipsis(column)}>
          <span
            class={`view-vital-value explore-col-text ${RATING_CLASS_MAP[this.getRating(configs, num)] ?? ''} ${ENABLED_TABLE_CONDITION_MENU_CLASS_NAME}`}
            data-col-id={column.colKey}
            data-row-id={renderCtx.getRowId(row)}
          >
            {text}
          </span>
        </div>
      </div>
    ) as unknown as SlotReturnValue;
  }

  /**
   * @description 按接口下发的评级阈值匹配评级（与详情侧 matchRating 同口径）：
   *              配置按上界升序，值 ≦ config.value 命中该档；不带 value 的配置为无上界兜底
   * @param {IRumFieldRatingConfig[]} configs 评级阈值配置
   * @param {number} value 指标值
   * @returns {string} 命中的评级标识
   */
  private getRating(configs: IRumFieldRatingConfig[], value: number): string {
    return (
      configs.find(config => config.value === undefined || value <= config.value)?.rating ??
      configs[configs.length - 1].rating
    );
  }

  /**
   * @description 数量统计单元格渲染：0 走灰色文本（无数据可下钻），大于 0 走红色下划线链接，点击切到 Span 视角检索该页面
   * @param {IRumSpanRecord} row 当前行数据
   * @param {BaseTableColumn} column 当前列配置项
   * @param {TableCellRenderContext} renderCtx 列渲染上下文
   * @returns {SlotReturnValue} 渲染dom
   */
  private renderCountCell(row: IRumSpanRecord, column: BaseTableColumn, renderCtx: TableCellRenderContext) {
    const value = Number(row?.[column.colKey]);
    const count = Number.isFinite(value) ? value : 0;
    const isLink = Boolean(count);
    /**
     * DOM 与评级列 / 内置 TEXT 列渲染器保持一致：explore-col 容器 + 省略容器 + 文本节点；
     * 零值与可下钻值仅类名、点击行为不同，保证单元格内边距、垂直居中与溢出表现一致。
     * 数量列右对齐由 view-count-col 主题类处理（explore-col 为 flex 容器，不继承 td 的 text-align）。
     */
    return (
      <div class='explore-col explore-text-col view-count-col'>
        <div class={renderCtx.isEnabledCellEllipsis(column)}>
          <span
            class={`view-count-value explore-col-text ${isLink ? 'is-link' : 'is-zero'}`}
            data-col-id={column.colKey}
            data-row-id={renderCtx.getRowId(row)}
            onClick={
              isLink
                ? (e: MouseEvent) => {
                    e.stopPropagation();
                    this.context.onViewCountClick(row, column.colKey);
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
