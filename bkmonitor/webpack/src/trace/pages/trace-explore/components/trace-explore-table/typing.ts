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

import type { OptionData, PrimaryTableCol, SlotReturnValue } from 'tdesign-vue-next';

/** 表格筛选项类型 */
export type TableFilterItem = OptionData;

export interface TableCellRenderContext<K extends string = string> {
  /** 开启省略文本省略的类名 */
  cellEllipsisClass: string;
  /** 不同类型单元格渲染策略对象集合 */
  cellRenderHandleMap: Record<ExploreTableColumnTypeEnum | K, TableCellRenderer>;
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

/** trace检索 表格列配置类型 */
export interface BaseTableColumn<K extends string = string, U extends Record<string, any> = Record<string, any>>
  extends Omit<PrimaryTableCol, 'ellipsis' | 'ellipsisTitle'> {
  /** 字段类型 */
  renderType?: K;
  /** 列描述(popover形式展现) **/
  headerDescription?: string;
  /** 单元格是否开启溢出省略弹出 popover 功能 */
  cellEllipsis?: boolean;
  /** 单元格后置插槽（tag类型列暂未支持） */
  suffixSlot?: TableCellRenderer;
  /** 需要自定义定义 渲染值 时可用 */
  getRenderValue?: (row, column: BaseTableColumn<any, any>) => GetTableCellRenderValue<K, U>;
  /** 点击列回调 -- 列类型为 ExploreTableColumnTypeEnum.CLICK 时可用 */
  clickCallback?: (row, column: BaseTableColumn<any, any>, event: MouseEvent) => void;
  /** 自定义单元格渲染 */
  cellRenderer?: TableCellRenderer;
}

export type ExploreTableColumn<T extends ExploreTableColumnTypeEnum | string = ExploreTableColumnTypeEnum> =
  BaseTableColumn<T, BaseTableCellRenderValueType>;

/**
 * @description 获取 table表格列 渲染值类型 (默认为字符串)
 *
 */
export type GetTableCellRenderValue<K, U = BaseTableCellRenderValueType> = K extends keyof U ? U[K] : string | string[];

export interface TagCellItem {
  alias: string;
  value: string;
  tagColor?: string;
  tagBgColor?: string;
}

/**  trace检索 table表格不同类型列 渲染值类型映射表 */
export interface BaseTableCellRenderValueType {
  [ExploreTableColumnTypeEnum.DURATION]: number;
  [ExploreTableColumnTypeEnum.TIME]: number;
  [ExploreTableColumnTypeEnum.TAGS]: string[] | TagCellItem[];
  [ExploreTableColumnTypeEnum.PREFIX_ICON]: {
    alias: string;
    prefixIcon: string | TableCellRenderer<ExploreTableColumn<ExploreTableColumnTypeEnum.PREFIX_ICON>>;
  };
  [ExploreTableColumnTypeEnum.LINK]: {
    alias: string;
    url: string;
  };
}

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
  /** 日期列 (将 时间戳 转换为 YYYY-MM-DD HH:mm:ss) */
  TIME = 'time',
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

/** 自定义显示列字段缓存配置 */
export interface CustomDisplayColumnFieldsConfig {
  displayFields: string[];
  fieldsWidth: { [colKey: string]: number };
}

/** 表格条件菜单项 */
export interface ExploreConditionMenuItem {
  /** 菜单 id */
  id: string;
  /** 菜单名称 */
  name: string;
  /** 菜单图标 */
  icon: string;
  /** 菜单点击回调 */
  onClick: (event: MouseEvent) => void;
  /** 菜单后缀icon渲染 */
  suffixRender?: () => SlotReturnValue;
}

/** 激活的条件菜单目标 */
export interface ActiveConditionMenuTarget {
  rowId: string;
  colId: string;
  conditionValue: string;
  customMenuList?: ExploreConditionMenuItem[];
}
