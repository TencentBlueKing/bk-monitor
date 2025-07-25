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
import type Vue from 'vue';
import type { VNode } from 'vue';

import type { TranslateResult } from 'vue-i18n';

export type CheckType = 'all' | 'current';

// 0 未选 1 半选 2 全选
export type CheckValue = 0 | 1 | 2;

export interface IAgentStatusData {
  count?: number;
  display: string | TranslateResult;
  errorCount?: number;
  status: string;
}

export interface IClassifyTab {
  active: string;
  list: { id: 'inner' | 'other' | 'outer'; name: TranslateResult }[];
}

export interface IEventsMap {
  [key: string]: Function;
}

export interface IipListParams {
  current: number;
  limit: number;
  tableKeyword: string;
}

export interface ILayoutComponents {
  [key: string]: Vue;
}

export interface IMenu {
  disabled?: boolean;
  hidden?: boolean;
  id: number | string;
  label: string | TranslateResult;
  readonly?: boolean;
}

export interface INodeData extends IMenu {
  children?: INodeData[];
  data: any; // 原始数据
}

export interface IPagination {
  count: number;
  current: number;
  limit: number;
}

// tab数据源
export interface IPanel {
  component?: Vue; // 组件对象（默认根据name从layout里面获取）
  disabled?: boolean; // tab是否禁用
  hidden?: boolean; // tab是否显示
  keepAlive?: boolean; // 是否缓存
  label: string | TranslateResult; // tab默认显示文本
  name: string; // tab唯一标识（要和components目录的文件名保持一致，作为后面动态组件的name）
  tips?: string | TranslateResult;
  type?: IpType; // 当前tab对于的类型（目前对于后端来说只有两种，只是前端选择方式不一样）
}

export type IPerateFunc = (item: IPreviewData) => IMenu[];

export interface IPreviewData {
  data: any[];
  dataNameKey?: string;
  id: IpType;
  name: string | TranslateResult;
}

export interface IPreviewDataOption {
  nameKey?: string;
}
export type IpType = 'DYNAMIC_GROUP' | 'INSTANCE' | 'SERVICE_TEMPLATE' | 'SET_TEMPLATE' | 'TOPO';

export interface ISearchData extends INodeData {
  path?: string;
}

export interface ISearchDataOption {
  idKey: string;
  nameKey: string;
  pathKey: string;
}

export interface ITableCheckData {
  checkType?: CheckType;
  checkValue?: CheckValue;
  excludeData?: any[];
  selections: any[];
}

/**
 *layout组件搜索函数的类型
 * @param params 接口参数
 */

export interface ITableConfig {
  hidden?: boolean;
  label: string | TranslateResult;
  minWidth?: number;
  prop: string;
  render?: (row: any, column: any, $index: number) => any | VNode;
}

export interface ITemplateDataOptions {
  childrenKey?: string;
  idKey?: string;
  labelKey?: string;
}

export interface ITreeNode {
  children: ITreeNode[];
  data?: any;
  id: number | string;
  level: number | string;
  name: string;
  parent?: ITreeNode;
}

export type SearchDataFuncType = (params: any, type?: string) => Promise<{ data: any[]; total: number }>;
