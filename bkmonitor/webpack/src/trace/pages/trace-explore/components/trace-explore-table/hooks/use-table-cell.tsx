/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
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

import { get, type MaybeRef } from '@vueuse/core';

import { formatDuration, formatTraceTableDate } from '../../../../../components/trace-view/utils/date';
import TagsCell from '../components/table-cell/tags-cell';
import {
  ENABLED_TABLE_CONDITION_MENU_CLASS_NAME,
  ENABLED_TABLE_ELLIPSIS_CELL_CLASS_NAME,
  TABLE_DEFAULT_CONFIG,
} from '../constants';
import {
  type BaseTableColumn,
  type ExploreTableColumn,
  ExploreTableColumnTypeEnum,
  type GetTableCellRenderValue,
  type TableCellRender,
} from '../typing';

import type { SlotReturnValue } from 'tdesign-vue-next';

export interface UseTableCellOptions {
  rowKeyField: MaybeRef<string>;
  cellEllipsisClass?: string;
  customCellRenderMap?: Record<string, TableCellRender>;
}
export function useTableCell({ rowKeyField, cellEllipsisClass, customCellRenderMap }: UseTableCellOptions) {
  /** table 默认配置项 */
  const { tableConfig: defaultTableConfig } = TABLE_DEFAULT_CONFIG;
  /** 不同类型单元格渲染策略对象集合 */
  let cellRenderHandleMap: Record<ExploreTableColumnTypeEnum | keyof typeof customCellRenderMap, TableCellRender> = {};

  /**
   * @description 初始化单元格渲染策略
   *
   */
  function initCellRenderHandleMap() {
    const defaultCellRenderHandleMap: Record<ExploreTableColumnTypeEnum, TableCellRender> = {
      [ExploreTableColumnTypeEnum.TAGS]: tagsColumnFormatter,
      [ExploreTableColumnTypeEnum.CLICK]: clickColumnFormatter,
      [ExploreTableColumnTypeEnum.PREFIX_ICON]: iconColumnFormatter,
      [ExploreTableColumnTypeEnum.TIME]: timeColumnFormatter,
      [ExploreTableColumnTypeEnum.DURATION]: durationColumnFormatter,
      [ExploreTableColumnTypeEnum.LINK]: linkColumnFormatter,
      [ExploreTableColumnTypeEnum.TEXT]: textColumnFormatter,
    };
    cellRenderHandleMap = {
      ...defaultCellRenderHandleMap,
      ...(customCellRenderMap || {}),
    };
  }

  /**
   * @description 获取当前行的唯一 rowId
   * @param row 当前行数据
   */
  function getRowId(row: Record<string, any>) {
    return row?.[get(rowKeyField)] || '';
  }

  /**
   * @description 是否启用单元格溢出省略弹出 popover
   * @returns {string} 开启单元格溢出省略弹出 popover 的类
   *
   */
  function isEnabledCellEllipsis(column: BaseTableColumn<any, any>) {
    if (column?.cellEllipsis === false) {
      return '';
    }
    return cellEllipsisClass || ENABLED_TABLE_ELLIPSIS_CELL_CLASS_NAME;
  }

  /**
   * @description 获取表格单元格渲染值（允许列通过 getRenderValue 自定义获取值逻辑）
   * @param row 当前行数据
   * @param {ExploreTableColumn} column 当前列配置项
   *
   */
  function getTableCellRenderValue<T extends ExploreTableColumnTypeEnum>(
    row,
    column: ExploreTableColumn<T>
  ): GetTableCellRenderValue<T> {
    const defaultGetRenderValue = row => {
      const alias = row?.[column.colKey];
      if (typeof alias !== 'object' || alias == null) {
        return alias;
      }
      return JSON.stringify(alias);
    };
    const getRenderValue = column?.getRenderValue || defaultGetRenderValue;
    return getRenderValue(row, column);
  }

  /**
   * @description 表格单元格后置插槽渲染
   *
   */
  function columnCellSuffixRender(column: BaseTableColumn<any, any>, row) {
    const suffixSlot = column?.suffixSlot;
    if (!suffixSlot) return null;
    return suffixSlot(row, column);
  }

  /**
   * @description ExploreTableColumnTypeEnum.CLICK  可点击触发回调 列渲染方法
   * @param {ExploreTableColumn} column 当前列配置项
   *
   */
  function clickColumnFormatter(column: ExploreTableColumn<ExploreTableColumnTypeEnum.CLICK>, row) {
    const alias = getTableCellRenderValue(row, column);
    return (
      <div class={'explore-col explore-click-col'}>
        <div class={`${isEnabledCellEllipsis(column)}`}>
          <span
            class='explore-click-text '
            onClick={event => column?.clickCallback?.(row, column, event)}
          >
            {alias}
          </span>
        </div>
        {columnCellSuffixRender(column, row)}
      </div>
    ) as unknown as SlotReturnValue;
  }

  /**
   * @description ExploreTableColumnTypeEnum.PREFIX_ICON  带有前置 icon 列渲染方法
   * @param {ExploreTableColumn} column 当前列配置项
   *
   */
  function iconColumnFormatter(column: ExploreTableColumn<ExploreTableColumnTypeEnum.PREFIX_ICON>, row) {
    const item = getTableCellRenderValue(row, column) || { alias: '', prefixIcon: '' };
    const { alias, prefixIcon } = item;
    if (alias == null || alias === '') {
      const textColumn = {
        ...column,
        getRenderValue: () => alias,
      };
      return textColumnFormatter(textColumn as unknown as ExploreTableColumn<ExploreTableColumnTypeEnum.TEXT>, row);
    }
    return (
      <div class='explore-col explore-prefix-icon-col'>
        {prefixIcon ? (
          typeof prefixIcon === 'string' ? (
            <i class={`prefix-icon ${prefixIcon}`} />
          ) : (
            prefixIcon(row, column)
          )
        ) : null}
        <div class={`${isEnabledCellEllipsis(column)}`}>
          <span
            class={`${ENABLED_TABLE_CONDITION_MENU_CLASS_NAME}`}
            data-col-id={column.colKey}
            data-row-id={getRowId(row)}
          >
            {alias}
          </span>
        </div>
        {columnCellSuffixRender(column, row)}
      </div>
    ) as unknown as SlotReturnValue;
  }

  /**
   * @description ExploreTableColumnTypeEnum.ELAPSED_TIME 日期时间列渲染方法 (将 时间戳 转换为 YYYY-MM-DD HH:mm:ss)
   * @param {ExploreTableColumn} column 当前列配置项
   *
   */
  function timeColumnFormatter(column: ExploreTableColumn<ExploreTableColumnTypeEnum.TIME>, row) {
    const timestamp = getTableCellRenderValue(row, column);
    const alias = formatTraceTableDate(timestamp);
    return (
      <div class={'explore-col explore-time-col'}>
        <div class={`${isEnabledCellEllipsis(column)}`}>
          <span
            class={`explore-time-text ${ENABLED_TABLE_CONDITION_MENU_CLASS_NAME}`}
            data-col-id={column.colKey}
            data-row-id={getRowId(row)}
          >
            {alias}
          </span>
        </div>
        {columnCellSuffixRender(column, row)}
      </div>
    ) as unknown as SlotReturnValue;
  }

  /**
   * @description ExploreTableColumnTypeEnum.DURATION 持续时间列渲染方法 (将 时间戳 自适应转换为 带单位的时间-例如 10s、10ms...)
   * @param {ExploreTableColumn} column 当前列配置项
   *
   */
  function durationColumnFormatter(column: ExploreTableColumn<ExploreTableColumnTypeEnum.DURATION>, row) {
    const timestamp = getTableCellRenderValue(row, column);
    const alias = formatDuration(+timestamp);
    return (
      <div class={'explore-col explore-duration-col '}>
        <div class={`${isEnabledCellEllipsis(column)}`}>
          <span
            class={`explore-duration-text ${ENABLED_TABLE_CONDITION_MENU_CLASS_NAME}`}
            data-col-id={column.colKey}
            data-row-id={getRowId(row)}
          >
            {alias}
          </span>
        </div>
        {columnCellSuffixRender(column, row)}
      </div>
    ) as unknown as SlotReturnValue;
  }

  /**
   * @description ExploreTableColumnTypeEnum.LINK  点击链接跳转列渲染方法
   * @param {ExploreTableColumn} column 当前列配置项
   *
   */
  function linkColumnFormatter(column: ExploreTableColumn<ExploreTableColumnTypeEnum.LINK>, row) {
    const item = getTableCellRenderValue(row, column);
    // 当url为空时，使用textColumnFormatter渲染为普通 text 文本样式
    if (!item?.url) {
      const textColumn = {
        ...column,
        getRenderValue: () => item?.alias,
      };
      return textColumnFormatter(textColumn as unknown as ExploreTableColumn<ExploreTableColumnTypeEnum.TEXT>, row);
    }
    return (
      <div class='explore-col explore-link-col '>
        <a
          style={{ color: 'inherit' }}
          href={item.url}
          rel='noreferrer'
          target='_blank'
        >
          <div class={`explore-link-text ${isEnabledCellEllipsis(column)}`}>
            <span>{item.alias}</span>
          </div>
          <i class='icon-monitor icon-mc-goto' />
        </a>
        {columnCellSuffixRender(column, row)}
      </div>
    ) as unknown as SlotReturnValue;
  }

  /**
   * @description ExploreTableColumnTypeEnum.TAGS 类型文本类型表格列渲染方法
   * @param {ExploreTableColumn} column 当前列配置项
   *
   */
  function tagsColumnFormatter(column: ExploreTableColumn<ExploreTableColumnTypeEnum.TAGS>, row) {
    const tags = getTableCellRenderValue(row, column);
    if (!tags?.length) {
      const textColumn = {
        ...column,
        getRenderValue: () => defaultTableConfig.emptyPlaceholder,
      };
      return textColumnFormatter(textColumn as unknown as ExploreTableColumn<ExploreTableColumnTypeEnum.TEXT>, row);
    }
    return (
      <TagsCell
        colId={column.colKey}
        column={column}
        rowId={getRowId(row)}
        tags={tags}
      />
    ) as unknown as SlotReturnValue;
  }

  /**
   * @description ExploreTableColumnTypeEnum.TEXT 类型文本类型表格列渲染方法
   * @param {ExploreTableColumn} column 当前列配置项
   *
   */
  function textColumnFormatter(column: ExploreTableColumn<ExploreTableColumnTypeEnum.TEXT>, row) {
    const alias = getTableCellRenderValue(row, column);
    return (
      <div class={'explore-col explore-text-col '}>
        <div class={`${isEnabledCellEllipsis(column)}`}>
          <span
            class={`explore-col-text ${ENABLED_TABLE_CONDITION_MENU_CLASS_NAME}`}
            data-col-id={column.colKey}
            data-row-id={getRowId(row)}
          >
            {alias == null || alias === '' ? defaultTableConfig.emptyPlaceholder : alias}
          </span>
        </div>
        {columnCellSuffixRender(column, row)}
      </div>
    ) as unknown as SlotReturnValue;
  }

  /**
   * @description 根据列类型，获取对应的表格列渲染方法
   * @param {ExploreTableColumn} column 当前列配置项
   *
   */
  function tableCellRender(
    column: BaseTableColumn<ExploreTableColumnTypeEnum | keyof typeof customCellRenderMap, any>,
    row
  ) {
    const renderType = column.renderType || ExploreTableColumnTypeEnum.TEXT;
    const renderMethod = cellRenderHandleMap[renderType];
    return renderMethod ? renderMethod(column, row) : null;
  }

  initCellRenderHandleMap();
  return {
    tableCellRender,
  };
}
