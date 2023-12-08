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
/*
 * @Author:
 * @Date: 2021-06-10 11:55:13
 * @LastEditTime: 2021-06-18 16:59:34
 * @LastEditors:
 * @Description:
 */
import { TranslateResult } from 'vue-i18n';

import type { TimeRangeType } from '../../components/time-range/time-range';

export interface IHostData {
  hosts: any[];
}

export interface IUserConfig {
  id?: number;
  value: string;
  key: string;
  username?: string;
}

export interface IPanelItem {
  icon: string;
  name: TranslateResult;
  key: string;
  num: number;
}

export interface IPanel {
  list: Array<IPanelItem>;
  active: string;
}

export interface IPanelStatistics {
  unresolveData: number;
  cpuData: number;
  menmoryData: number;
  diskData: number;
}

export type Dictionary = {
  [prop: string]: any;
};

export interface ITableRow extends Object {
  rowId: string; // 当前行ID
  mark: boolean; // 是否有置顶标记
  selection: boolean; // 当前行是否check
  [prop: string]: any;
}

export interface IOption {
  name: any;
  id?: string | number;
  value?: string | number;
  children?: IOption[];
}

export interface ITableOptions {
  stickyValue?: object;
  panelKey?: string;
}

export interface IConditionValue {
  condition: '>' | '>=' | '<' | '<=' | '=';
  value: number;
}

export type FieldValue = string | number | (string | number)[] | IConditionValue[] | (string | number)[][];

export interface IFieldConfig {
  name: TranslateResult; // 字段中文名称
  id: string; // 字段
  checked?: boolean; // 是否展示该列
  disable?: boolean; // 是否禁用操作
  filterChecked?: boolean; // 是否展示在筛选面板
  filterDisable?: boolean; // 是否禁用操作
  options?: Array<IOption>; // 选项列表
  conditions?: IOption[]; // 条件
  value?: FieldValue; // 当前值
  type: InputType; // 值类型
  fuzzySearch?: boolean; // 是否支持模糊搜索
  multiple?: boolean; // 多选（select类型有效，如 集群和模块 字段）
  show?: boolean; // 筛选面板是否展示条件
  dynamic?: boolean; // 是否是动态字段
}

export type CheckValue = 0 | 1 | 2; // 0: 无选择 1: 半选 2: 全选
export type CheckType = 'current' | 'all'; // current: 本页选择；all: 跨页选择
export interface ICheck {
  type: CheckType;
  value: CheckValue;
}

export interface IPageConfig {
  page: number;
  pageSize: number;
  pageList: number[];
  total: number;
}

export interface ISort {
  order: 'ascending' | 'descending';
  prop: string;
}

export type InputType = 'select' | 'textarea' | 'checkbox' | 'condition' | 'number' | 'text' | 'cascade';

export interface ISelectedValues {
  selectedGroup: string[];
  unSelectedGroup: string[];
}

export interface ISearchItem {
  id: string;
  value: FieldValue;
}

export type View = 'process' | 'host';

export interface IGroupItem {
  id: string;
  key?: string;
  title: string;
  hidden: boolean;
  match_type?: ('manual' | 'auto')[];
}
export interface IHostGroup {
  id: string;
  title: string;
  panels: IGroupItem[];
  type?: string;
  auto_rules?: string[];
  manual_list?: string[];
}

export interface IDragItem {
  itemId: string;
  groupId: string;
}

export interface IHostInfo {
  title: TranslateResult;
  value: string | string[];
  id: string;
  copy?: boolean;
  link?: boolean;
}

export interface IHostDetailParams {
  ip: string;
  cloudId: string;
  processId: string;
  osType: string | number;
}

export interface ITag {
  id: string;
  name: TranslateResult;
  value: any;
  display: string;
  count: number;
  conditions?: IOption[];
  // 原始值类型
  originValue: FieldValue;
  dynamic?: boolean;
}

export type ViewType = 'host' | 'process';

export type ChartType = 0 | 1 | 2;
export interface ICompareOption {
  type: 'none' | 'target' | 'time' | 'metric';
  value: string[] | string | boolean;
}

export interface IToolsOption {
  timeRange: TimeRangeType;
  refleshInterval: string[] | number;
  searchValue?: any;
}
export interface IQueryOption {
  compare: ICompareOption;
  tools: IToolsOption;
  type?: ICompareChangeType;
}

export interface ISearchTipsObj {
  show: boolean;
  time: number;
  showSplit: boolean;
  value: boolean;
  showAddStrategy: boolean;
}

export interface ISearchSelectList {
  name: string;
  id: number | string;
  children?: ISearchSelectList[];
}

export type ICompareChangeType = 'compare' | 'search' | 'interval' | 'timeRange';
