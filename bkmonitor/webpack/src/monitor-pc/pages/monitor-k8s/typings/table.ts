export interface IFilterDict {
  [key: string]: (number | string)[];
}
export interface IFilterItem {
  text: string;
  value: number | string;
}
export interface ILinkItem {
  disabledClick?: boolean; // 禁用点击且不为蓝色
  display_value?: string;
  icon?: string; // 前置icon 使用base64 或者 iconfont
  key?: string;
  syncTime?: boolean; // 同步时间跳转
  target?: LinkItemTarget;
  url: string;
  value: string;
}
export interface IPermission {
  [key: string]: boolean;
}
export interface IProgressItem {
  label: string; // title
  status: string; // SUCCESS: #18c0a1 FAILED: #ea3636 NODATA: #dcdee5
  value: number; // 0-100
}
export interface IStackLinkItem extends ILinkItem {
  is_stack?: boolean;
  subtitle?: string;
}
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
// tag 类型数据类型
export interface ITagItem {
  key: string;
  value: string;
}
// self 为内部框架跳转  blank为新开窗口跳转 event 触发本地事件
export type LinkItemTarget = 'blank' | 'event' | 'null_event' | 'self';
export const progressColor = {
  SUCCESS: '#18c0a1',
  FAILED: '#ea3636',
  NODATA: '#dcdee5',
};

// 表格排序类型
export type ColumnSort = 'ascending' | 'custom' | 'descending';

// 收藏列
export interface ICollectItem {
  api: string; // 收藏api
  is_collect: boolean; // 是否收藏
  params: any; // 调用收藏接口所需参数
}
/* 关联类型 */
export interface IRelationItem {
  label: string; // 标签
  name: string; // 标签后的文本
}
// 作用域插槽类型(不可配置型)
export interface IScopedSlotItem {
  // 此类型只需传入slotid即可， 父组件对应使用scopedSlots={{ slotId: (row) => .... }}
  slotId: string; // this.$scopedSlots?.[slotId].(row)
}
export interface ITabelDataFilterItem {
  icon?: string; // base64
  id: string;
  name: string;
}
// 表格字段描述
export interface ITableColumn {
  // 当前列 权限
  actionId?: string;
  // 是否需要异步加载
  asyncable?: boolean;
  checked?: boolean;
  // 常驻列 不可取消勾选列
  disabled?: boolean;
  // 过滤数据选项
  filter_list?: IFilterItem[];
  // 选中的数据过滤项
  filter_value?: (number | string)[];
  // 是否可以过滤数据选项
  filterable?: boolean;
  // 是否固定列 left | right
  fixed?: TableColumnFixed;
  // 头部icon
  header_pre_icon?: string;
  // 字段id
  id: string;
  // 最大列宽 必须配合自定义calcColumnWidth方法使用
  max_width?: number;
  // 最小列宽
  min_width?: number;
  // 字段名称
  name: string;
  // 其他属性
  props?: Record<string, any>;
  // 是否伸缩大小
  resizable?: boolean;
  // 是否需要溢出提示
  showOverflowTooltip?: boolean;
  // 是否可以排序
  sortable?: 'custom' | boolean;
  // 字段类型
  type: TableColumnType;
  // 列宽
  width?: number;
  // renderHeader
  renderHeader?: () => any;
}
// 表格api返回数据类型
export interface ITableData {
  // checkbox filter
  check_filter?: ITabelDataFilterItem[];
  // 是否可以勾选
  checkable?: boolean;
  // 表格字段
  columns: ITableColumn[];
  // 表格数据
  data: TableRow[];
  // 头部筛选列表
  filter: ITabelDataFilterItem[];
  // 表格概览数据行
  overview_data: TableRow;
  // 总数
  total: number;
  // // 标题栏设置
  // header?: {
  //   title?: string; // 标题
  //   link?: ILinkItem; // 标题右侧的链接
  // }
}
/** 表格过滤条件 */
export interface ITableFilterItem {
  icon?: string;
  id: string;
  name: number | string;
  status?: ITableItemStatus;
  tips?: string; // tooltips
}

// 表格数据每一个字段的数据类型
export type ITableItem<T extends TableColumnType> = Pick<ITableItemMap, T>[T];

export interface ITableItemMap {
  // 收藏
  collect: ICollectItem;
  // id
  id: number | string;
  // key - value 类型
  kv: ITagItem[];
  // 链接
  link: ILinkItem;
  // 多个链接
  link_list: ILinkItem[];
  // 列表
  list: string[];
  // 操作 （点击弹出选择项 格式和多个链接一样）
  more_operate: ILinkItem[];
  // number类型
  number: number | { color?: string; unit: string; value: number };
  permission?: IPermission;
  // 进度条
  progress: IProgressItem;
  // 关联类型
  relation: IRelationItem[];
  // 作用域插槽
  scoped_slots: IScopedSlotItem;
  // 堆栈链接
  stack_link: IStackLinkItem;
  // 字符串类型
  string: { icon?: string; text: string; type: string };
  // 标签
  tag: string[];
  // 时间
  time: number | string;
  // data_status
  data_status: {
    icon: string;
  };
  // datapoints
  datapoints: {
    datapoints: [number, number][];
    unit: string;
    unitDecimal?: number;
    valueTitle?: string;
  };
  // status
  status: {
    text: string;
    tips?: string;
    type: ITableItemStatus;
  };
}
/** 正常 | 异常 | 成功状态 | 失败状态 | 禁用状态 | 等待*/
export type ITableItemStatus =
  | 'disabled'
  | 'failed'
  | 'NODATA'
  | 'normal'
  | 'stoped'
  | 'SUCCESS'
  | 'success'
  | 'waiting'
  | 'warning';
export interface ITablePagination {
  count: number;
  current: number;
  limit: number;
  showTotalCount?: boolean;
}
// 固定列位置
export type TableColumnFixed = 'left' | 'right';

// 字段数据类型
export type TableColumnType =
  | 'collect'
  | 'data_status'
  | 'datapoints'
  | 'id'
  | 'kv'
  | 'link'
  | 'link_list'
  | 'list'
  | 'more_operate'
  | 'number'
  | 'permission'
  | 'progress'
  | 'relation'
  | 'scoped_slots'
  | 'stack_link'
  | 'status'
  | 'string'
  | 'tag'
  | 'time';
// 表格分页类型
export type TablePaginationType = 'normal' | 'simple';
// 表格行数据类型
export type TableRow = Record<string, ITableItem<TableColumnType>>;
// 表格大小设置类型
export type TableSizeType = 'large' | 'medium' | 'small';
