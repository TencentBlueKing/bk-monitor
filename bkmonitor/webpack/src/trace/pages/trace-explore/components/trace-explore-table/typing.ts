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

import type { OptionData, PrimaryTableCol, SlotReturnValue } from 'tdesign-vue-next';
import type { TippyOptions } from 'vue-tippy';

/**
 * @description trace检索 table表格列类型 枚举
 */
export enum ExploreTableColumnTypeEnum {
  /** 可点击触发回调列 */
  CLICK = 'click',
  /** 持续时间 (将 时间戳 自适应转换为 带单位的时间-例如 10s、10ms...) */
  DURATION = 'duration',
  /** 链接跳转 */
  LINK = 'link',
  /** 前置icon */
  PREFIX_ICON = 'prefix-icon',
  /** 标签列 */
  TAGS = 'tags',
  /** 纯文本  */
  TEXT = 'text',
  /** 日期列 (将 时间戳 转换为 YYYY-MM-DD HH:mm:ssZZ) */
  TIME = 'time',
  /** 用户名展示标签列(已兼容多租户逻辑) */
  USER_TAGS = 'user-tags',
}

/** 检索表格loading类型枚举 */
export enum ExploreTableLoadingEnum {
  /** 刷新 -- table body 部分 显示 骨架屏 效果loading */
  BODY_SKELETON = 'table_body_skeleton',
  /** 刷新 -- table header 部分 显示 骨架屏 效果loading */
  HEADER_SKELETON = 'table_header_skeleton',
  /** 滚动 -- 显示 表格底部 loading */
  SCROLL = 'scrollLoading',
}

/** 激活的条件菜单目标 */
export interface ActiveConditionMenuTarget {
  colId: string;
  conditionValue: string;
  customMenuList?: ExploreConditionMenuItem[];
  rowId: string;
}

/**  trace检索 table表格不同类型列 渲染值类型映射表 */
export interface BaseTableCellRenderValueType {
  [ExploreTableColumnTypeEnum.DURATION]: number;
  [ExploreTableColumnTypeEnum.TAGS]: string[] | TagCellItem[];
  [ExploreTableColumnTypeEnum.TIME]: number;
  [ExploreTableColumnTypeEnum.USER_TAGS]: string[];
  [ExploreTableColumnTypeEnum.LINK]: {
    alias: string;
    url: string;
  };
  [ExploreTableColumnTypeEnum.PREFIX_ICON]: {
    alias: string;
    prefixIcon: string | TableCellRenderer<ExploreTableColumn<ExploreTableColumnTypeEnum.PREFIX_ICON>>;
  };
}

/** 不同类型单元格的私有属性映射 */
export interface BaseTableCellSpecificPropsMap {
  /** tag 类型单元格私有属性 */
  [ExploreTableColumnTypeEnum.TAGS]: {
    /** 溢出标签提示popover内容渲染 */
    ellipsisTip?: (ellipsisList: any[] | string[]) => SlotReturnValue;
    /** 标签溢出时溢出标签hover显示的提示popover配置选项 */
    ellipsisTippyOptions?: TippyOptions;
  };
  // 其他类型公共列有需求可以按需添加
}

/** trace检索 表格列配置类型 */
export interface BaseTableColumn<K extends string = string, U extends Record<string, any> = Record<string, any>>
  extends Omit<PrimaryTableCol, 'ellipsis' | 'ellipsisTitle'> {
  /** 单元格是否开启溢出省略弹出 popover 功能 */
  cellEllipsis?: boolean;
  /** 自定义单元格渲染 */
  cellRenderer?: TableCellRenderer;
  /** 非公共属性，不同单元格类型各自特定属性配置 */
  cellSpecificProps?: GetTableCellSpecificProps<K>;
  /** 列描述(popover形式展现) **/
  headerDescription?: string;
  /** 字段类型 */
  renderType?: K;
  /** 单元格后置插槽（tag类型列暂未支持） */
  suffixSlot?: TableCellRenderer;
  /** 点击列回调 -- 列类型为 ExploreTableColumnTypeEnum.CLICK 时可用 */
  clickCallback?: (row, column: BaseTableColumn<any, any>, event: MouseEvent) => void;
  /** 需要自定义定义 渲染值 时可用 */
  getRenderValue?: (row, column: BaseTableColumn<any, any>) => GetTableCellRenderValue<K, U>;
}

/** 表格条件菜单项 */
export interface ExploreConditionMenuItem {
  /** 菜单图标 */
  icon: string;
  /** 菜单 id */
  id: string;
  /** 菜单名称 */
  name: string;
  /** 菜单点击回调 */
  onClick: (event: MouseEvent) => void;
  /** 菜单后缀icon渲染 */
  suffixRender?: () => SlotReturnValue;
}

export type ExploreTableColumn<T extends ExploreTableColumnTypeEnum | string = ExploreTableColumnTypeEnum> =
  BaseTableColumn<T, BaseTableCellRenderValueType>;

/**
 * @description 获取 table表格列 渲染值类型 (默认为字符串)
 *
 */
export type GetTableCellRenderValue<K, U = BaseTableCellRenderValueType> = K extends keyof U
  ? U[K]
  : string | string[] | unknown;

/**
 * @description 获取 table表格不同类型单元格列 的私有属性类型
 *
 */
export type GetTableCellSpecificProps<K> = K extends keyof BaseTableCellSpecificPropsMap
  ? BaseTableCellSpecificPropsMap[K]
  : Record<string, any>;

export interface TableCellRenderContext<K extends string = string> {
  /** 开启省略文本省略的类名 */
  cellEllipsisClass: string;
  /** 不同类型单元格渲染策略对象集合 */
  cellRenderHandleMap: Record<ExploreTableColumnTypeEnum | K, TableCellRenderer>;
  /** 获取当前行的唯一 rowId */
  getRowId: (row: Record<string, any>) => string;
  /** 获取表格单元格渲染值 */
  getTableCellRenderValue: <T extends ExploreTableColumnTypeEnum | string>(
    row: Record<string, any>,
    column: BaseTableColumn<any, any>
  ) => GetTableCellRenderValue<T>;
  /** 是否启用单元格文本省略号 */
  isEnabledCellEllipsis: (column: BaseTableColumn<any, any>) => string;
}

/**
 * 通用表格单元格渲染类型
 * column 允许为 BaseTableColumn 或 ExploreTableColumn，row 为 any
 */
export type TableCellRenderer<T extends BaseTableColumn<any, any> = BaseTableColumn<any, any>> = (
  row: any,
  column: T,
  renderCtx: TableCellRenderContext
) => SlotReturnValue;

/** 表格筛选项类型 */
export type TableFilterItem = OptionData;

export interface TagCellItem {
  alias: string;
  tagBgColor?: string;
  tagColor?: string;
  tagHoverBgColor?: string;
  tagHoverColor?: string;
  value: string;
}
