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
import type VueI18n from 'vue-i18n';

export type CompareMap = {
  [p in CompareOptions]: VueI18n.TranslateResult;
};

export type CompareOptions = 'WEEKLY' | 'YESTERDAY';

export interface ICompare {
  type: string;
  value: number;
}

export interface ICompareData {
  avg: number;
  current: number;
  max: number;
  min: number;
  name: string;
  total: number;
}

export interface IConfig {
  label: string;
  prop: string;
  span: number;
}

export interface IContent {
  [propName: string]: any;
}

export interface IDropdownMenu {
  options: IOptions[];
  value: number;
}

export interface IOptions {
  text: VueI18n.TranslateResult;
  value: number;
}

export interface ISelectGroup {
  active: number;
  list: ISelectItem[];
}

export interface ISelectItem {
  text: VueI18n.TranslateResult;
  value: number;
}

export interface ISeriesData {
  data: Array<object>;
  name: string;
}
