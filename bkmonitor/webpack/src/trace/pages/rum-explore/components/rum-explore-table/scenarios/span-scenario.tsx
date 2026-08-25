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
 * documentation files (the "Software"), to deal in the Software without restriction, including without limitation the
 * rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
 * permit persons to whom the Software is furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all copies or substantial portions of
 * the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
 * THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
 * CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
 * THE SOFTWARE.
 */

import { get } from '@vueuse/core';

import {
  type BaseTableColumn,
  type TableCellRenderContext,
  type TableCellRenderer,
  ExploreTableColumnTypeEnum,
} from '../../../../trace-explore/components/trace-explore-table/typing';
import {
  DURATION_COLOR_THRESHOLDS,
  RUM_LINK_FIELDS,
  RUM_STATUS_CODE_MAP,
  RUM_TIME_FIELDS,
  SPAN_TYPE_FIELD,
  SPAN_TYPE_META,
} from '../../../constants';
import { BaseScenario } from './base-scenario';

import type { SlotReturnValue } from 'tdesign-vue-next';

/**
 * @class SpanScenario
 * @classdesc Span 检索场景：时间列、链接列、类型列、状态码列的渲染差异在 columnOverrides 中声明；
 *           耗时（单位=微秒）等基于字段元数据的渲染推导在 buildBaseline 中完成。
 * @extends BaseScenario
 */
export class SpanScenario extends BaseScenario {
  readonly privateClassName = 'span-table';
  readonly rowKey = 'span_id';
  protected columnOverrides: Record<string, BaseTableColumn> = {
    /** 时间列：复用内置时间渲染 */
    ...Object.fromEntries(
      [...RUM_TIME_FIELDS].map((key): [string, BaseTableColumn] => [
        key,
        { renderType: ExploreTableColumnTypeEnum.TIME },
      ])
    ),
    /** 链接列：点击把值加为检索条件 */
    ...Object.fromEntries(
      [...RUM_LINK_FIELDS].map((key): [string, BaseTableColumn] => [
        key,
        {
          renderType: ExploreTableColumnTypeEnum.CLICK,
          clickCallback: (row, _column, _event) => this.context.onCellFilter(key, `${row?.[key] ?? ''}`),
        },
      ])
    ),
    /** Span 类型列：类型图标 + 类型名 */
    [SPAN_TYPE_FIELD]: {
      renderType: ExploreTableColumnTypeEnum.PREFIX_ICON,
      getRenderValue: row => this.getSpanTypeRenderValue(row[SPAN_TYPE_FIELD]),
    },
    /** 状态码列：按状态语义着色的 Tag */
    'status.code': {
      renderType: ExploreTableColumnTypeEnum.TAGS,
      getRenderValue: row => this.getStatusCodeRenderValue(row['status.code']),
    },
  };

  constructor(
    protected readonly context: {
      /** 点击链接类单元格，把值加为检索条件 */
      onCellFilter: (colKey: string, value: string) => void;
    } & BaseScenario['context']
  ) {
    super(context);
  }

  /**
   * @description 场景元数据推导：Span 中单位为微秒（us）的字段按耗时渲染（三色着色）
   * @param {string} colKey 列键
   * @returns 声明式列配置（仅渲染/交互相关）
   */
  protected buildBaseline(colKey: string): Partial<BaseTableColumn> {
    const field = get(this.context.fieldMap).get(colKey);
    if (field?.field_unit === 'us') {
      return { cellRenderer: this.renderDurationCell };
    }
    return {};
  }

  // ----------------- Span 场景私有渲染方法 -----------------
  /**
   * @description Span 耗时单元格渲染：复用内置 DURATION 格式化（阈值/单位），再按自身耗时阈值套用三色主题
   */
  renderDurationCell: TableCellRenderer = (row, column: BaseTableColumn, renderCtx: TableCellRenderContext) => {
    const inner = renderCtx?.cellRenderHandleMap?.[ExploreTableColumnTypeEnum.DURATION]?.(row, column, renderCtx);
    const value = (row as Record<string, unknown>)?.[column.colKey];
    if (value == null || value === '') return inner;
    const microseconds = Number(value);
    let theme = 'normal';
    if (microseconds >= DURATION_COLOR_THRESHOLDS.warning) {
      theme = 'failed';
    } else if (microseconds >= DURATION_COLOR_THRESHOLDS.normal) {
      theme = 'warning';
    }
    return (<span class={['custom-duration-col', `is-${theme}`]}>{inner}</span>) as unknown as SlotReturnValue;
  };

  // ----------------- Span 场景私有逻辑方法 -----------------

  /**
   * @description Span 类型列渲染值：类型图标 + 类型别名（复用内置前置图标渲染）
   * @param {unknown} value 当前行 Span 类型值
   */
  private getSpanTypeRenderValue(value: unknown) {
    const meta = SPAN_TYPE_META[value as string];
    return {
      alias: meta?.label || value,
      prefixIcon: meta?.icon
        ? () =>
            (
              <img
                class='span-type-icon'
                alt=''
                src={meta.icon}
              />
            ) as unknown as SlotReturnValue
        : '',
    };
  }

  /**
   * @description 状态码列渲染值：按状态语义着色的 Tag（复用内置 tags 渲染）
   * @param {unknown} value 当前行状态码值
   */
  private getStatusCodeRenderValue(value: unknown) {
    const status = RUM_STATUS_CODE_MAP[Number(value)];
    return status ? [{ alias: status.alias, tagBgColor: status.tagBgColor, tagColor: status.tagColor }] : [];
  }
}
