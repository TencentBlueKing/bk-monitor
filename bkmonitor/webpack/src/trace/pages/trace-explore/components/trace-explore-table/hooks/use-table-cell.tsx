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

import { type MaybeRef, get } from '@vueuse/core';

import { formatDuration, formatTraceTableDate } from '../../../../../components/trace-view/utils/date';
import TagsCell from '../components/table-cell/tags-cell';
import {
  ENABLED_TABLE_CONDITION_MENU_CLASS_NAME,
  ENABLED_TABLE_ELLIPSIS_CELL_CLASS_NAME,
  TABLE_DEFAULT_CONFIG,
} from '../constants';
import { type ExploreTableColumn, type GetTableCellRenderValue, ExploreTableColumnTypeEnum } from '../typing';

import type { SlotReturnValue } from 'tdesign-vue-next';

export function useTableCell(rowKeyField: MaybeRef<string>) {
  /** table 默认配置项 */
  const { tableConfig: defaultTableConfig } = TABLE_DEFAULT_CONFIG;

  /**
   * @description 获取当前行的唯一 rowId
   * @param row 当前行数据
   */
  function getRowId(row: Record<string, any>) {
    return row?.[get(rowKeyField)] || '';
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
  function columnCellSuffixRender(column, row) {
    const suffixSlot = column?.suffixSlot;
    if (!suffixSlot) {
      return null;
    }
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
        <div class={`${ENABLED_TABLE_ELLIPSIS_CELL_CLASS_NAME}`}>
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
        <div class={`${ENABLED_TABLE_ELLIPSIS_CELL_CLASS_NAME}`}>
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
        <div class={`${ENABLED_TABLE_ELLIPSIS_CELL_CLASS_NAME}`}>
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
        <div class={`${ENABLED_TABLE_ELLIPSIS_CELL_CLASS_NAME}`}>
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
          <div class={`explore-link-text ${ENABLED_TABLE_ELLIPSIS_CELL_CLASS_NAME}`}>
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
        <div class={`${ENABLED_TABLE_ELLIPSIS_CELL_CLASS_NAME}`}>
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
  function handleSetFormatter(column: ExploreTableColumn, row: Record<string, any>) {
    switch (column.renderType) {
      case ExploreTableColumnTypeEnum.CLICK:
        return clickColumnFormatter(column as ExploreTableColumn<ExploreTableColumnTypeEnum.CLICK>, row);
      case ExploreTableColumnTypeEnum.PREFIX_ICON:
        return iconColumnFormatter(column as ExploreTableColumn<ExploreTableColumnTypeEnum.PREFIX_ICON>, row);
      case ExploreTableColumnTypeEnum.TIME:
        return timeColumnFormatter(column as ExploreTableColumn<ExploreTableColumnTypeEnum.TIME>, row);
      case ExploreTableColumnTypeEnum.DURATION:
        return durationColumnFormatter(column as ExploreTableColumn<ExploreTableColumnTypeEnum.DURATION>, row);
      case ExploreTableColumnTypeEnum.LINK:
        return linkColumnFormatter(column as ExploreTableColumn<ExploreTableColumnTypeEnum.LINK>, row);
      case ExploreTableColumnTypeEnum.TAGS:
        return tagsColumnFormatter(column as ExploreTableColumn<ExploreTableColumnTypeEnum.TAGS>, row);
      default:
        return textColumnFormatter(column as ExploreTableColumn<ExploreTableColumnTypeEnum.TEXT>, row);
    }
  }

  return {
    tableCellRender: handleSetFormatter,
  };
}
