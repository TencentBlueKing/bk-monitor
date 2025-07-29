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

/** 激活的条件菜单目标 */
export interface ActiveConditionMenuTarget {
  colId: string;
  conditionValue: string;
  customMenuList?: ExploreConditionMenuItem[];
  rowId: string;
}

/** 自定义显示列字段缓存配置 */
export interface CustomDisplayColumnFieldsConfig {
  displayFields: string[];
  fieldsWidth: { [colKey: string]: number };
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

/** trace检索 表格列配置类型 */
export interface ExploreTableColumn<T extends ExploreTableColumnTypeEnum = ExploreTableColumnTypeEnum>
  extends PrimaryTableCol {
  /** 列描述(popover形式展现) **/
  headerDescription?: string;
  /** 字段类型 */
  renderType?: T;
  /** 点击列回调 -- 列类型为 ExploreTableColumnTypeEnum.CLICK 时可用 */
  clickCallback?: (row, column: ExploreTableColumn<ExploreTableColumnTypeEnum.CLICK>, event: MouseEvent) => void;
  /** 需要自定义定义 渲染值 时可用 */
  getRenderValue?: (row, column: ExploreTableColumn<T>) => GetTableCellRenderValue<T>;
  /** 单元格后置插槽（tag类型列暂未支持） */
  suffixSlot?: (row, column: ExploreTableColumn) => SlotReturnValue;
}

/**
 * @description 获取 table表格列 渲染值类型 (默认为字符串)
 *
 */
export type GetTableCellRenderValue<T> = T extends keyof TableCellRenderValueType
  ? TableCellRenderValueType[T]
  : string;

/**  trace检索 table表格不同类型列 渲染值类型映射表 */
export interface TableCellRenderValueType {
  [ExploreTableColumnTypeEnum.DURATION]: number;
  [ExploreTableColumnTypeEnum.TIME]: number;
  [ExploreTableColumnTypeEnum.LINK]: {
    alias: string;
    url: string;
  };
  [ExploreTableColumnTypeEnum.PREFIX_ICON]: {
    alias: string;
    prefixIcon: ((row, column: ExploreTableColumn<ExploreTableColumnTypeEnum.PREFIX_ICON>) => SlotReturnValue) | string;
  };
  [ExploreTableColumnTypeEnum.TAGS]: {
    alias: string;
    tagBgColor: string;
    tagColor: string;
    value: string;
  }[];
}

/** 表格筛选项类型 */
export type TableFilterItem = OptionData;
