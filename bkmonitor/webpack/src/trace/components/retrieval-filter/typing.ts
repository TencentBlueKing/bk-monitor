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

import type { PropType } from 'vue';

export enum EMode {
  queryString = 'queryString',
  ui = 'ui',
}
export enum EFieldType {
  all = 'all',
  date = 'date',
  integer = 'integer',
  keyword = 'keyword',
  text = 'text',
}

export enum EMethod {
  eq = 'eq',
  exclude = 'exclude',
  include = 'include',
  ne = 'ne',
}

export const METHOD_MAP = {
  [EMethod.eq]: '=',
  [EMethod.exclude]: window.i18n.tc('不包含'),
  [EMethod.include]: window.i18n.tc('包含'),
  [EMethod.ne]: '!=',
};

export enum APIType {
  APM = 'apm', // apm
  MONITOR = 'monitor', // monitor default
}

export interface IFilterField {
  name: string;
  alias: string;
  type: EFieldType;
  is_option_enabled: boolean; // 是否可自定选项
  is_dimensions?: boolean;
  supported_operations: {
    alias: string;
    value: EMethod;
    options?: {
      label: string;
      name: string;
    };
  }[]; // 支持的操作
}

export enum ECondition {
  and = 'and',
}

export interface IWhereItem {
  key: string;
  condition: ECondition;
  method: EMethod | string;
  value: string[];
  options?: {
    is_wildcard: boolean;
  };
}

export interface IGetValueFnParams {
  limit?: number;
  where?: IWhereItem[];
  fields?: string[];
  queryString?: string;
}

export interface IWhereValueOptionsItem {
  count: number;
  list: {
    id: string;
    name: string;
  }[];
}

export interface IFilterItem {
  key: { id: string; name: string };
  condition: { id: ECondition; name: string };
  method: { id: EMethod; name: string };
  value: { id: string; name: string }[];
  options?: {
    is_wildcard: boolean;
  };
  hide?: boolean;
  isSetting?: boolean; // 是否是设置项
}

interface FavList {
  config: any;
  create_user: string;
  group_id: number | object;
  id: number;
  name: string;
  update_time: string;
  update_user: string;
  disabled?: boolean;
  groupName?: string;
}

export interface IFavoriteListItem {
  id: string;
  name: string;
  favorites: {
    name: string;
    config: {
      queryConfig: {
        query_string: string;
        where: IWhereItem[];
      };
    };
  }[];
}

export const RETRIEVAL_FILTER_PROPS = {
  fields: {
    type: Array as PropType<IFilterField[]>,
    default: () => [],
  },
  getValueFn: {
    type: Function as PropType<(params: IGetValueFnParams) => Promise<IWhereValueOptionsItem>>,
    default: () =>
      Promise.resolve({
        count: 0,
        list: [],
      }),
  },
  where: {
    type: Array as PropType<IWhereItem[]>,
    default: () => [],
  },
  commonWhere: {
    type: Array as PropType<IWhereItem[]>,
    default: () => [],
  },
  queryString: {
    type: String as PropType<string>,
    default: '',
  },
  selectFavorite: {
    type: Object as PropType<FavList>,
    default: () => null,
  },
  favoriteList: {
    type: Array as PropType<IFavoriteListItem[]>,
    default: () => [],
  },
  residentSettingOnlyId: {
    type: String as PropType<string>,
    default: '',
  },
  dataId: {
    type: String as PropType<string>,
    default: '',
  },
  source: {
    type: String as PropType<APIType>,
    default: APIType.MONITOR,
  },
  filterMode: {
    type: String as PropType<EMode>,
    default: EMode.ui,
  },
  isShowFavorite: {
    type: Boolean as PropType<boolean>,
    default: false,
  },
  defaultShowResidentBtn: {
    type: Boolean as PropType<boolean>,
    default: false,
  },
};
export const RETRIEVAL_FILTER_EMITS = {
  favorite: (_isEdit: boolean) => {},
  whereChange: (_v: IWhereItem[]) => {},
  queryStringChange: (_v: string) => {},
  modeChange: (_v: EMode) => {},
  queryStringInputChange: (_v: string) => {},
  commonWhereChange: (_where: IWhereItem[]) => {},
  showResidentBtnChange: (_v: boolean) => {},
  search: () => {},
} as const;
export const UI_SELECTOR_PROPS = {
  fields: {
    type: Array as PropType<IFilterField[]>,
    default: () => [],
  },
  getValueFn: {
    type: Function as PropType<(params: IGetValueFnParams) => Promise<IWhereValueOptionsItem>>,
    default: () =>
      Promise.resolve({
        count: 0,
        list: [],
      }),
  },
  value: {
    type: Array as PropType<IFilterItem[]>,
    default: () => [],
  },
  clearKey: {
    type: String as PropType<string>,
    default: '',
  },
};
export const UI_SELECTOR_EMITS = {
  change: (_v: IFilterItem[]) => {},
} as const;
