/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
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

export interface IAlarmGroupList {
  id: number | string;
  name: string;
  receiver: string[];
}
export interface ICategoryItem {
  category: string;
  category_alias?: string;
  checked: boolean;
  children?: ITempLateItem[];
  indeterminate: boolean;
  system: string;
  system_alias?: string;
}
export interface ITempLateItem {
  category: string;
  category_alias?: string;
  checked?: boolean;
  code?: string;
  has_been_applied?: boolean; // 已配置
  icon?: string;
  id: number;
  monitor_type?: string;
  name: string;
  strategy?: { id: string; name: string }; // 已配置策略
  system: string;
  system_alias?: string;
  type: string;
}

export type TTemplateList<T = ITempLateItem> = {
  category?: boolean;
  category_alias?: string;
  children?: T[];
  name: string;
  system: string;
  system_alias?: string;
};
