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

// 收藏项类型定义
export interface IFavoriteItem {
  id?: number;
  created_by?: string;
  space_uid?: number;
  index_set_id?: number;
  name?: string;
  group_id?: number;
  visible_type?: 'private' | 'public' | 'unknown';
  params?: IParams;
  is_active?: boolean;
  is_actives?: boolean[];
  index_set_names?: string[];
  index_set_ids?: string[]; // union 类型时
  display_fields: string[];
  index_set_type?: 'single' | 'union';
  favorite_type?: string;
  updated_by?: string;
  created_at?: string;
  [key: string]: any;
}

// 搜索参数类型
export interface IParams {
  addition: Array<{
    field: string;
    operator: string;
    value: { [x: string]: any }[] | number[];
  }>;
  chart_params: Record<string, any>;
  ip_chooser: Record<string, any>;
  keyword: string;
  search_fields: any[];
  host_scopes?: any[];
}

// 收藏分组类型
export interface IGroupItem {
  group_id: number | string;
  group_name: string;
  group_type?: 'private' | 'public' | 'unknown' | string;
  favorites: IFavoriteItem[];
}

// Tab 列表项类型
export interface ITabItem {
  name: string;
  icon: string;
  key: string;
  count: number;
}

// 工具栏规则类型
export interface IValidationRule {
  validator?: (val: any) => boolean;
  message: string;
  trigger: string;
  required?: boolean;
  max?: number;
}

export type IGroupNameRules = Record<string, IValidationRule[]>;

// 组件 Props 类型
export interface ICollectListProps {
  list: IGroupItem[];
  loading: boolean;
  isCollapse: boolean;
}

export interface ICollectToolProps {
  isChecked: boolean;
  collapseAll: boolean;
  rules: IGroupNameRules;
}

export interface IMenuItem {
  key: string;
  label: string;
}

// 事件类型
export interface IFavoriteEvents {
  refresh: () => void;
  'select-item': (item: IFavoriteItem | null) => void;
  'show-change': (value: boolean) => void;
  'width-change': (width: number) => void;
  handle: (type: string, data: any) => void;
  'tab-change': (tab: string) => void;
  collapse: (value: boolean) => void;
}

// 状态管理类型
export interface IFavoriteState {
  isShow: boolean;
  collectWidth: number;
  favoriteLoading: boolean;
  activeTab: string;
  isShowCurrentIndexList: boolean;
  searchValue: string;
  isCollapseList: boolean;
  activeFavorite: IFavoriteItem | null;
  expandedMap: Record<string, boolean>;
  selectedId: null | number;
}

// API 响应类型
export interface IApiResponse<T = any> {
  code: number;
  message: string;
  data: T;
  result: boolean;
}

// 排序选项类型
export interface ISortOption {
  name: string;
  id: string;
}

// 搜索模式类型
export type SearchMode = 'sql' | 'ui';

// 索引集类型
export type IndexSetType = 'single' | 'union';
