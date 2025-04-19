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

import type { TranslateResult } from 'vue-i18n';

/** 表格排序类型 */
export interface TableSort {
  /** 排序字段名 */
  field: string;
  /** 排序方式 */
  order: 'asc' | 'desc' | null;
}

/** 表格筛选项类型 */
export interface TableFilterItem {
  /** 筛选项名称 */
  label: string;
  /** 筛选项值 */
  value: boolean | number | string;
}

/** 表格筛选项变更事件类型 */
export interface TableFilterChangeEvent {
  /** 筛选项字段 */
  field: string;
  /** 筛选项值 */
  values: Array<boolean | number | string>;
  /** 筛选项列表 */
  filterList: TableFilterItem[];
}

/** trace检索 表格列配置类型 */
export interface ExploreTableColumn<T extends ExploreTableColumnTypeEnum> {
  /** 字段类型 */
  type?: T;
  /** 字段id */
  field: string;
  /** 字段名称（渲染指标列时为指标名称） */
  alias: TranslateResult;
  /** 列宽 */
  width?: number;
  /** 最小列宽 */
  minWidth?: number;
  /** 是否固定列 */
  fixed?: 'left' | 'right';
  /** 列渲染顺序权重 */
  order?: number;
  /** 是否允许列排序 */
  sortable?: boolean;
  /** 列筛选项 */
  filter?: TableFilterItem[];
  /** 是否多选筛选项 */
  filterMultiple?: boolean;
  /** 内容过长时显示为省略号 */
  showOverflow?: 'ellipsis' | 'title' | 'tooltip';
  /** 列对齐方式 */
  align?: 'center' | 'left' | 'right';
  /** 需要自定义定义 渲染值 时可用 */
  getRenderValue?: (row, column: ExploreTableColumn<T>) => GetTableCellRenderValue<T>;
  /** 点击列回调 -- 列类型为 ExploreTableColumnTypeEnum.CLICK 时可用 */
  clickCallback?: (row, column: ExploreTableColumn<ExploreTableColumnTypeEnum.CLICK>, event: MouseEvent) => void;
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
  [ExploreTableColumnTypeEnum.TAGS]: {
    alias: string;
    tagColor: string;
    tagBgColor: string;
  }[];
  [ExploreTableColumnTypeEnum.PREFIX_ICON]: {
    alias: string;
    prefixIcon: string;
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
  /** 刷新 -- 显示 骨架屏 效果loading */
  REFRESH = 'refreshLoading',
  /** 滚动 -- 显示 表格底部 loading */
  SCROLL = 'scrollLoading',
}
