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
import type { TimeRangeType } from '../../components/time-range/time-range';
/*
 * @Author:
 * @Date: 2021-06-10 11:55:13
 * @LastEditTime: 2021-06-18 16:59:34
 * @LastEditors:
 * @Description:
 */
import type { TranslateResult } from 'vue-i18n';

export type ChartType = 0 | 1 | 2;

export type CheckType = 'all' | 'current'; // current: 本页选择；all: 跨页选择

export type CheckValue = 0 | 1 | 2; // 0: 无选择 1: 半选 2: 全选

export type Dictionary = {
  [prop: string]: any;
};

export type FieldValue = (number | string)[] | (number | string)[][] | IConditionValue[] | number | string;

export interface ICheck {
  type: CheckType;
  value: CheckValue;
}

export type ICompareChangeType = 'compare' | 'interval' | 'search' | 'timeRange';

export interface ICompareOption {
  type: 'metric' | 'none' | 'target' | 'time';
  value: boolean | string | string[];
}

export interface IConditionValue {
  condition: '<' | '<=' | '=' | '>' | '>=';
  value: number;
}

export interface IDragItem {
  groupId: string;
  itemId: string;
}

export interface IFieldConfig {
  allowEmpt?: boolean; // 是否允许为空
  checked?: boolean; // 是否展示该列
  conditions?: IOption[]; // 条件
  disable?: boolean; // 是否禁用操作
  dynamic?: boolean; // 是否是动态字段
  filterChecked?: boolean; // 是否展示在筛选面板
  filterDisable?: boolean; // 是否禁用操作
  fuzzySearch?: boolean; // 是否支持模糊搜索
  id: string; // 字段
  multiple?: boolean; // 多选（select类型有效，如 集群和模块 字段）
  name: TranslateResult; // 字段中文名称
  options?: Array<IOption>; // 选项列表
  show?: boolean; // 筛选面板是否展示条件
  type: InputType; // 值类型
  value?: FieldValue; // 当前值
}

export interface IGroupItem {
  hidden: boolean;
  id: string;
  key?: string;
  match_type?: ('auto' | 'manual')[];
  title: string;
}

export interface IHostData {
  hosts: any[];
}
export interface IHostDetailParams {
  cloudId: string;
  ip: string;
  osType: number | string;
  processId: string;
}
export interface IHostGroup {
  auto_rules?: string[];
  id: string;
  manual_list?: string[];
  panels: IGroupItem[];
  title: string;
  type?: string;
}

export interface IHostInfo {
  copy?: boolean;
  id: string;
  link?: boolean;
  title: TranslateResult;
  value: string | string[];
}

export type InputType = 'cascade' | 'checkbox' | 'condition' | 'number' | 'select' | 'text' | 'textarea';

export interface IOption {
  children?: IOption[];
  id?: number | string;
  name: any;
  value?: number | string;
}

export interface IPageConfig {
  page: number;
  pageList: number[];
  pageSize: number;
  total: number;
}

export interface IPanel {
  active: string;
  list: Array<IPanelItem>;
}

export interface IPanelItem {
  icon: string;
  key: string;
  name: TranslateResult;
  num: number;
}

export interface IPanelStatistics {
  cpuData: number;
  diskData: number;
  menmoryData: number;
  unresolveData: number;
}
export interface IQueryOption {
  compare: ICompareOption;
  tools: IToolsOption;
  type?: ICompareChangeType;
}

export interface ISearchItem {
  id: string;
  value: FieldValue;
}

export interface ISearchSelectList {
  children?: ISearchSelectList[];
  id: number | string;
  name: string;
}

export interface ISearchTipsObj {
  show: boolean;
  showAddStrategy: boolean;
  showSplit: boolean;
  time: number;
  value: boolean;
}

export interface ISelectedValues {
  selectedGroup: string[];
  unSelectedGroup: string[];
}

export interface ISort {
  order: 'ascending' | 'descending';
  prop: string;
}

export interface ITableOptions {
  panelKey?: string;
  stickyValue?: object;
}
export interface ITableRow {
  [prop: string]: any;
  mark: boolean; // 是否有置顶标记
  rowId: string; // 当前行ID
  selection: boolean; // 当前行是否check
}

export interface ITag {
  conditions?: IOption[];
  count: number;
  display: string;
  dynamic?: boolean;
  id: string;
  name: TranslateResult;
  // 原始值类型
  originValue: FieldValue;
  value: any;
}
export interface IToolsOption {
  refreshInterval: number | string[];
  searchValue?: any;
  timeRange: TimeRangeType;
}

export interface IUserConfig {
  id?: number;
  key: string;
  username?: string;
  value: string;
}

export type View = 'host' | 'process';

export type ViewType = 'host' | 'process';
