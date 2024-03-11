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

import { TranslateResult } from 'vue-i18n';

export enum ViewModeType {
  Table = 'table',
  Combine = 'combine',
  Flame = 'flame',
  Topo = 'topo'
}

export enum TextDirectionType {
  Ltr = 'ltr',
  Rtl = 'rtl'
}

export interface ViewModeItem {
  id: ViewModeType;
  icon: string;
}

export interface ProfilingTableItem {
  id: number;
  name: string;
  self: number;
  total: number;
  displaySelf?: string;
  displayTotal?: string;
  location?: string;
  color?: string;
  diff?: string;
  baseline?: number;
  comparison?: number;
  mark?: string;
}

export interface TableColumn {
  id: string;
  name: string | TranslateResult;
  sort?: string;
  mode?: 'normal' | 'diff';
}

export interface ITableTipsDetail {
  left?: number; // 提示框左边距离画布左边的距离
  top?: number; // 提示框上边距离画布上边的距离
  title?: string;
  self?: number;
  total?: number;
  baseline?: number;
  comparison?: number;
  mark?: string;
  displaySelf?: string;
  displayTotal?: string;
  selfPercent?: string;
  totalPercent?: string;
  proportion?: string | number;
  duration?: string;
  diffDuration?: string;
  diffValue?: number | string;
  id?: string;
}

export interface IQueryParams {
  bk_biz_id?: number;
  app_name?: string;
  service_name?: string;
  start?: number;
  end?: number;
  data_type?: string;
  profile_id?: string;
  diff_profile_id?: string;
  offset?: number;
  diagram_types?: string[];
  sort?: string;
  filter_labels?: Record<string, string>;
  diff_filter_labels?: any;
  is_compared?: boolean;
}

export interface DataTypeItem {
  key: string;
  name: string;
}
