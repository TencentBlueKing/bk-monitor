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

export enum EType {
  day = 2,
  hour = 5,
  month = 4,
  once = 1,
  week = 3,
}

export enum EWeek {
  Fri = 5,
  Mon = 1,
  Sat = 6,
  Sun = 7,
  Thu = 4,
  Tue = 2,
  Wed = 3,
}

export interface IAddChartToolData {
  active: string;
  show: boolean;
  tabList: any;
}

export interface IChartDataItem {
  fatherId?: string;
  id: number;
  key?: string;
  title: string;
}

export interface IChartListAllItem {
  bk_biz_id?: number;
  id: number;
  name: string;
  panels: IChartDataItem[];
  text: string;
  title?: string;
  uid: string;
}

export interface IContentFormData {
  contentDetails: string;
  contentTitle: string;
  curBizId?: string;
  curGrafana?: string;
  curGrafanaName?: string;
  graphs: string[];
  height?: number;
  rowPicturesNum: 1 | 2;
  width?: number;
}

export interface IDefaultRadioList {
  id: string;
  text: string;
  title: string;
}

export interface IGraphValueItem {
  id: string;
  name: string;
}

export interface IRadioMap {
  id: number;
  name: string | TranslateResult;
}

export interface ISelectChartValue {
  bkBizId: number;
  dashboardUid: number;
  panelId: number;
  title?: string;
}

export interface ITableColumnItem {
  formatter?: Function;
  key: string;
  label: string | TranslateResult;
  overflow?: boolean;
  width?: number;
}

export interface ITimePeriodValue {
  dayList: number[];
  hour: number;
  runTime: string;
  type: EType;
  weekList: number[];
}

export interface IToolTabListItem {
  label: string;
  name: 'default' | 'grafana';
}
