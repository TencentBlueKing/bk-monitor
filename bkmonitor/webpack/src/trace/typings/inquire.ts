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
  app_alias: string;
  app_name: string;
  application_id: number;
  permission: Record<string, string>;
}

export interface IScopeOption {
  id: string;
  options: { id: string; name: string }[];
}
export interface IScopeSelect {
  /* 范围查询动态表单选项 */ id: string;
  key: string;
  metric_key: string;
  name: string;
  trace_key: string;
  value: string[];
}

// 收藏列表
export declare namespace IFavList {
  // eslint-disable-next-line @typescript-eslint/naming-convention
  interface favList {
    config: any;
    id?: number;
    name?: string;
  }
  interface IEvent {
    deleteFav?: number;
    selectFav?: any;
  }
  interface IProps {
    checkedValue: favList;
    value: favList[];
  }
}

export interface IAppItem {
  app_alias: string;
  app_name: string;
  application_id: number;
  is_enabled_profiling?: boolean;
}
export interface IFavoriteItem {
  config: any;
  id: number | string;
  name: string;
}

export interface ISearchSelectItem {
  async: boolean;
  children: { id: string; name: string }[];
  id: string;
  multiple: boolean;
  name: string;
  placeholder: string;
  validate: boolean;
}

export interface ISearchSelectValue {
  id: string;
  name?: string;
  values: { id: string; name: string }[];
}

export interface ISearchTypeItem {
  id: SearchType;
  name: string;
}

export type SearchType = 'accurate' | 'scope';
