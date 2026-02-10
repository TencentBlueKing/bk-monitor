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

import { type MaybeRef, get } from '@vueuse/core';

import { formatDuration, formatTraceTableDate } from '../../../../../components/trace-view/utils/date';
import TagsCell from '../components/table-cell/tags-cell';
import UserTagsCell from '../components/table-cell/user-tags-cell';
import {
  ENABLED_TABLE_CONDITION_MENU_CLASS_NAME,
  ENABLED_TABLE_ELLIPSIS_CELL_CLASS_NAME,
  TABLE_DEFAULT_CONFIG,
} from '../constants';
import {
  type BaseTableColumn,
  type ExploreTableColumn,
  type GetTableCellRenderValue,
  type TableCellRenderContext,
  type TableCellRenderer,
  ExploreTableColumnTypeEnum,
} from '../typing';

import type { SlotReturnValue } from 'tdesign-vue-next';

export interface UseTableCellOptions {
  /** 是否启用单元格文本省略号 */
  cellEllipsisClass?: string;
  /** 自定义单元格渲染策略对象集合 */
  customCellRenderMap?: Record<string, TableCellRenderer>;
  /** 表格行数据唯一key字段名 */
  rowKeyField: MaybeRef<string>;
  /** 默认单元格数据取值逻辑 */
  customDefaultGetRenderValue?: (row, column: BaseTableColumn<any, any>) => string | string[];
}
export function useTableCell({
  rowKeyField,
  cellEllipsisClass,
  customCellRenderMap,
  customDefaultGetRenderValue,
}: UseTableCellOptions) {
  /** table 默认配置项 */
  const { tableConfig: defaultTableConfig } = TABLE_DEFAULT_CONFIG;
  /** 不同类型单元格渲染策略对象集合 */
  let cellRenderHandleMap: Record<ExploreTableColumnTypeEnum | keyof typeof customCellRenderMap, TableCellRenderer> =
    {};

  /** table 单元格渲染上下文信息 */
  const renderContext: TableCellRenderContext<keyof typeof customCellRenderMap> = {
    cellEllipsisClass: cellEllipsisClass || ENABLED_TABLE_ELLIPSIS_CELL_CLASS_NAME,
    cellRenderHandleMap,
    isEnabledCellEllipsis,
    getRowId,
    getTableCellRenderValue,
  };

  /**
   * @description 初始化单元格渲染策略
   *
   */
  function initCellRenderHandleMap() {
    const defaultCellRenderHandleMap: Record<ExploreTableColumnTypeEnum, TableCellRenderer> = {
      [ExploreTableColumnTypeEnum.TAGS]: tagsColumnFormatter,
      [ExploreTableColumnTypeEnum.USER_TAGS]: userTagsColumnFormatter,
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
    renderContext.cellRenderHandleMap = cellRenderHandleMap;
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
    return renderContext.cellEllipsisClass;
  }

  /**
   * @description 判断值是否为空
   */
  function isEmpty(value: unknown) {
    return value == null || value === '';
  }

  /**
   * @description 获取表格单元格渲染值（允许列通过 getRenderValue 自定义获取值逻辑）
   * @param row 当前行数据
   * @param {ExploreTableColumn} column 当前列配置项
   *
   */
  function getTableCellRenderValue<T extends ExploreTableColumnTypeEnum | string>(
    row,
    column: ExploreTableColumn<T>
  ): GetTableCellRenderValue<T> {
    const defaultGetRenderValue = row => row?.[column.colKey];
    const getRenderValue = column?.getRenderValue || customDefaultGetRenderValue || defaultGetRenderValue;
    return getRenderValue(row, column);
  }

  /**
   * @description 表格单元格后置插槽渲染
   *
   */
  function columnCellSuffixRender(
    row,
    column: BaseTableColumn<any, any>,
    renderCtx: TableCellRenderContext<keyof typeof customCellRenderMap>
  ) {
    const suffixSlot = column?.suffixSlot;
    if (!suffixSlot) return null;
    return suffixSlot(row, column, renderCtx);
  }

  /**
   * @description ExploreTableColumnTypeEnum.CLICK  可点击触发回调 列渲染方法
   * @param {ExploreTableColumn} column 当前列配置项
   *
   */
  function clickColumnFormatter(
    row,
    column: ExploreTableColumn<ExploreTableColumnTypeEnum.CLICK>,
    renderCtx: TableCellRenderContext<keyof typeof customCellRenderMap>
  ) {
    const alias = getTableCellRenderValue(row, column);
    if (isEmpty(alias)) {
      return textColumnFormatter(
        row,
        column as unknown as ExploreTableColumn<ExploreTableColumnTypeEnum.TEXT>,
        renderCtx
      );
    }
    return (
      <div class={'explore-col explore-click-col'}>
        <div class={`${renderCtx.isEnabledCellEllipsis(column)}`}>
          <span
            class='explore-click-text '
            onClick={event => column?.clickCallback?.(row, column, event)}
          >
            {alias}
          </span>
        </div>
        {columnCellSuffixRender(row, column, renderCtx)}
      </div>
    ) as unknown as SlotReturnValue;
  }

  /**
   * @description ExploreTableColumnTypeEnum.PREFIX_ICON  带有前置 icon 列渲染方法
   * @param {ExploreTableColumn} column 当前列配置项
   *
   */
  function iconColumnFormatter(
    row,
    column: ExploreTableColumn<ExploreTableColumnTypeEnum.PREFIX_ICON>,
    renderCtx: TableCellRenderContext<keyof typeof customCellRenderMap>
  ) {
    const item = getTableCellRenderValue(row, column) || { alias: '', prefixIcon: '' };
    const { alias, prefixIcon } = item;
    if (isEmpty(alias)) {
      const textColumn = {
        ...column,
        getRenderValue: () => alias,
      };
      return textColumnFormatter(
        row,
        textColumn as unknown as ExploreTableColumn<ExploreTableColumnTypeEnum.TEXT>,
        renderCtx
      );
    }
    return (
      <div class='explore-col explore-prefix-icon-col'>
        {prefixIcon ? (
          typeof prefixIcon === 'string' ? (
            <i class={`prefix-icon ${prefixIcon}`} />
          ) : (
            prefixIcon(row, column, renderCtx)
          )
        ) : null}
        <div class={`${renderCtx.isEnabledCellEllipsis(column)}`}>
          <span
            class={`${ENABLED_TABLE_CONDITION_MENU_CLASS_NAME}`}
            data-col-id={column.colKey}
            data-row-id={getRowId(row)}
          >
            {alias}
          </span>
        </div>
        {columnCellSuffixRender(row, column, renderCtx)}
      </div>
    ) as unknown as SlotReturnValue;
  }

  /**
   * @description ExploreTableColumnTypeEnum.ELAPSED_TIME 日期时间列渲染方法 (将 时间戳 转换为 YYYY-MM-DD HH:mm:ssZZ)
   * @param {ExploreTableColumn} column 当前列配置项
   *
   */
  function timeColumnFormatter(
    row,
    column: ExploreTableColumn<ExploreTableColumnTypeEnum.TIME>,
    renderCtx: TableCellRenderContext<keyof typeof customCellRenderMap>
  ) {
    const timestamp = getTableCellRenderValue(row, column);
    if (!timestamp) {
      return textColumnFormatter(
        row,
        column as unknown as ExploreTableColumn<ExploreTableColumnTypeEnum.TEXT>,
        renderCtx
      );
    }
    const alias = formatTraceTableDate(timestamp);
    return (
      <div class={'explore-col explore-time-col'}>
        <div class={`${renderCtx.isEnabledCellEllipsis(column)}`}>
          <span
            class={`explore-time-text ${ENABLED_TABLE_CONDITION_MENU_CLASS_NAME}`}
            data-col-id={column.colKey}
            data-row-id={getRowId(row)}
          >
            {alias}
          </span>
        </div>
        {columnCellSuffixRender(row, column, renderCtx)}
      </div>
    ) as unknown as SlotReturnValue;
  }

  /**
   * @description ExploreTableColumnTypeEnum.DURATION 持续时间列渲染方法 (将 时间戳 自适应转换为 带单位的时间-例如 10s、10ms...)
   * @param {ExploreTableColumn} column 当前列配置项
   *
   */
  function durationColumnFormatter(
    row,
    column: ExploreTableColumn<ExploreTableColumnTypeEnum.DURATION>,
    renderCtx: TableCellRenderContext<keyof typeof customCellRenderMap>
  ) {
    const timestamp = getTableCellRenderValue(row, column);
    if (!timestamp) {
      return textColumnFormatter(
        row,
        column as unknown as ExploreTableColumn<ExploreTableColumnTypeEnum.TEXT>,
        renderCtx
      );
    }
    const alias = formatDuration(+timestamp);
    return (
      <div class={'explore-col explore-duration-col '}>
        <div class={`${renderCtx.isEnabledCellEllipsis(column)}`}>
          <span
            class={`explore-duration-text ${ENABLED_TABLE_CONDITION_MENU_CLASS_NAME}`}
            data-col-id={column.colKey}
            data-row-id={getRowId(row)}
          >
            {alias}
          </span>
        </div>
        {columnCellSuffixRender(row, column, renderCtx)}
      </div>
    ) as unknown as SlotReturnValue;
  }

  /**
   * @description ExploreTableColumnTypeEnum.LINK  点击链接跳转列渲染方法
   * @param {ExploreTableColumn} column 当前列配置项
   *
   */
  function linkColumnFormatter(
    row,
    column: ExploreTableColumn<ExploreTableColumnTypeEnum.LINK>,
    renderCtx: TableCellRenderContext<keyof typeof customCellRenderMap>
  ) {
    const item = getTableCellRenderValue(row, column);
    // 当url为空时，使用textColumnFormatter渲染为普通 text 文本样式
    if (!item?.url) {
      const textColumn = {
        ...column,
        getRenderValue: () => item?.alias,
      };
      return textColumnFormatter(
        row,
        textColumn as unknown as ExploreTableColumn<ExploreTableColumnTypeEnum.TEXT>,
        renderCtx
      );
    }
    return (
      <div class='explore-col explore-link-col '>
        <a
          style={{ color: 'inherit' }}
          href={item.url}
          rel='noreferrer'
          target='_blank'
        >
          <div class={`explore-link-text ${renderCtx.isEnabledCellEllipsis(column)}`}>
            <span>{item.alias}</span>
          </div>
          <i class='icon-monitor icon-mc-goto' />
        </a>
        {columnCellSuffixRender(row, column, renderCtx)}
      </div>
    ) as unknown as SlotReturnValue;
  }

  /**
   * @description ExploreTableColumnTypeEnum.TAGS 类型 tag标签类型 表格列渲染方法
   * @param {ExploreTableColumn} column 当前列配置项
   *
   */
  function tagsColumnFormatter(
    row,
    column: ExploreTableColumn<ExploreTableColumnTypeEnum.TAGS>,
    renderCtx: TableCellRenderContext<keyof typeof customCellRenderMap>
  ) {
    const tags = getTableCellRenderValue(row, column);
    if (!tags?.length) {
      const textColumn = {
        ...column,
        getRenderValue: () => defaultTableConfig.emptyPlaceholder,
      };
      return textColumnFormatter(
        row,
        textColumn as unknown as ExploreTableColumn<ExploreTableColumnTypeEnum.TEXT>,
        renderCtx
      );
    }
    return (
      <TagsCell
        colId={column.colKey}
        column={column}
        renderCtx={renderCtx}
        rowId={getRowId(row)}
        tags={tags}
      />
    ) as unknown as SlotReturnValue;
  }

  /**
   * @description ExploreTableColumnTypeEnum.USER_TAGS 类型 用户名展示标签类型 表格列渲染方法(兼容多租户逻辑)
   * @param {ExploreTableColumn} column 当前列配置项
   *
   */
  function userTagsColumnFormatter(
    row,
    column: ExploreTableColumn<ExploreTableColumnTypeEnum.USER_TAGS>,
    renderCtx: TableCellRenderContext<keyof typeof customCellRenderMap>
  ) {
    const userTags = getTableCellRenderValue(row, column);
    if (!userTags?.length) {
      const textColumn = {
        ...column,
        getRenderValue: () => defaultTableConfig.emptyPlaceholder,
      };
      return textColumnFormatter(
        row,
        textColumn as unknown as ExploreTableColumn<ExploreTableColumnTypeEnum.TEXT>,
        renderCtx
      );
    }
    return (
      <UserTagsCell
        colId={column.colKey}
        column={column}
        renderCtx={renderCtx}
        rowId={getRowId(row)}
        tags={userTags}
      />
    ) as unknown as SlotReturnValue;
  }

  /**
   * @description ExploreTableColumnTypeEnum.TEXT 类型文本类型表格列渲染方法
   * @param {ExploreTableColumn} column 当前列配置项
   *
   */
  function textColumnFormatter(
    row,
    column: ExploreTableColumn<ExploreTableColumnTypeEnum.TEXT>,
    renderCtx: TableCellRenderContext<keyof typeof customCellRenderMap>
  ) {
    const alias = getTableCellRenderValue(row, column);
    return (
      <div class={'explore-col explore-text-col '}>
        <div class={`${renderCtx.isEnabledCellEllipsis(column)}`}>
          <span
            class={`explore-col-text ${ENABLED_TABLE_CONDITION_MENU_CLASS_NAME}`}
            data-col-id={column.colKey}
            data-row-id={getRowId(row)}
          >
            {isEmpty(alias) ? defaultTableConfig.emptyPlaceholder : alias}
          </span>
        </div>
        {columnCellSuffixRender(row, column, renderCtx)}
      </div>
    ) as unknown as SlotReturnValue;
  }

  /**
   * @description 根据列类型，获取对应的表格列渲染方法
   * @param {ExploreTableColumn} column 当前列配置项
   *
   */
  function tableCellRender(
    row,
    column: BaseTableColumn<ExploreTableColumnTypeEnum | keyof typeof customCellRenderMap, any>,
    renderCtx: TableCellRenderContext<keyof typeof customCellRenderMap>
  ) {
    const renderType = column.renderType || ExploreTableColumnTypeEnum.TEXT;
    const renderMethod = cellRenderHandleMap[renderType];
    return renderMethod ? renderMethod(row, column, renderCtx) : null;
  }

  initCellRenderHandleMap();
  return {
    tableCellRender,
    isEnabledCellEllipsis,
    renderContext,
  };
}
