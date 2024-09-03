/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition):
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

export interface IAppItem {
  application_id: number;
  app_alias: string;
  app_name: string;
  permission: Record<string, string>;
}

export interface IScopeSelect {
  /* 范围查询动态表单选项 */ id: string;
  metric_key: string;
  name: string;
  trace_key: string;
  value: string[];
  key: string;
}
export interface IScopeOption {
  id: string;
  options: { id: string; name: string }[];
}

// 收藏列表
export declare namespace IFavList {
  // eslint-disable-next-line @typescript-eslint/naming-convention
  interface favList {
    name?: string;
    config: any;
    id?: number;
  }
  interface IProps {
    value: favList[];
    checkedValue: favList;
  }
  interface IEvent {
    deleteFav?: number;
    selectFav?: any;
  }
}

export interface IAppItem {
  application_id: number;
  app_alias: string;
  app_name: string;
  is_enabled_profiling?: boolean;
}
export type SearchType = 'accurate' | 'scope';

export interface ISearchTypeItem {
  id: SearchType;
  name: string;
}

export interface IFavoriteItem {
  id: number | string;
  name: string;
  config: any;
}

export interface ISearchSelectItem {
  id: string;
  name: string;
  multiple: boolean;
  placeholder: string;
  async: boolean;
  validate: boolean;
  children: { id: string; name: string }[];
}

export interface ISearchSelectValue {
  id: string;
  name?: string;
  values: { id: string; name: string }[];
}
