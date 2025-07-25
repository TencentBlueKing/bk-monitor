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

export interface IHeader {
  condition?: Array<any>;
  conditionList?: Array<any>;
  dropdownShow?: boolean;
  keyword?: string;
  keywordObj?: IFilterData[];
  list?: Array<any>;
  value?: number;
  handleSearch: () => void;
}
export interface ILabel {
  isSelected: boolean;
  noticeName: string;
  selectedLabels: any;
  serviceCategory: string;
  target: any;
  value?: string;
}
export interface IPopover {
  data: any;
  edit: boolean;
  hover: number;
  index?: number;
  instance: any;
  status: string;
}

export interface IStrategyConfigProps {
  actionName?: string;
  bkCloudId?: number | string;
  bkEventGroupId?: number;
  bkStrategyId?: Array<{ id: number | string; name: number | string }>;
  dataSource?: Array<any>;
  fromRouteName?: string;
  ip?: string;
  isFta?: boolean;
  keywords?: string[];
  metricId?: string;
  noticeName?: string;
  pluginId?: string;
  resultTableId?: string;
  serviceCategory?: string;
  strategyLabels?: string;
  strategyType?: string;
  taskId?: number | string;
  timeSeriesGroupId?: number;
}
export interface ITableInstance {
  data?: Array<any>;
  keyword?: string;
  page?: number;
  pageList?: Array<string>;
  pageSize?: number;
  total?: number;
}
interface IFilterData {
  id: number | string; // 所属分组ID
  name: TranslateResult; // 分组名称
  values: any[]; // 勾选数据
}
