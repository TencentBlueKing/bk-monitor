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

export enum TextDirectionType {
  Ltr = 'ltr',
  Rtl = 'rtl',
}

export enum ViewModeType {
  Combine = 'combine',
  Flame = 'flame',
  Table = 'table',
  Topo = 'topo',
}

export interface DataTypeItem {
  default_agg_method?: string;
  key: string;
  name: string;
}

export interface IQueryParams {
  agg_method?: string;
  app_name?: string;
  bk_biz_id?: number;
  data_type?: string;
  diagram_types?: string[];
  diff_filter_labels?: any;
  diff_profile_id?: string;
  end?: number;
  filter_labels?: Record<string, string>;
  is_compared?: boolean;
  offset?: number;
  profile_id?: string;
  service_name?: string;
  sort?: string;
  start?: number;
}

export interface ITableTipsDetail {
  baseline?: number;
  comparison?: number;
  diff?: number;
  diffDuration?: string;
  diffValue?: number | string;
  displaySelf?: string;
  displayTotal?: string;
  duration?: string;
  id?: string;
  left?: number; // 提示框左边距离画布左边的距离
  mark?: string;
  proportion?: number | string;
  self?: number;
  selfPercent?: string;
  title?: string;
  top?: number; // 提示框上边距离画布上边的距离
  total?: number;
  totalPercent?: string;
}

export interface ProfilingTableItem {
  baseline?: number;
  color?: string;
  comparison?: number;
  diff?: number;
  displaySelf?: string;
  displayTotal?: string;
  id: number;
  location?: string;
  mark?: string;
  name: string;
  self: number;
  total: number;
}

export interface TableColumn {
  id: string;
  mode?: 'diff' | 'normal';
  name: string | TranslateResult;
  sort?: string;
}

export interface ViewModeItem {
  icon: string;
  id: ViewModeType;
  label: string;
}
