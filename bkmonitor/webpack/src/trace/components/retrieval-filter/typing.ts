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

export const fieldTypeMap = {
  all: {
    name: window.i18n.tc('数字'),
    icon: 'icon-monitor icon-a-',
    color: '#979BA5',
    bgColor: '#E8EAF0',
  },
  integer: {
    name: window.i18n.tc('数字'),
    icon: 'icon-monitor icon-number1',
    color: '#60A087',
    bgColor: '#DDEBE6',
  },
  keyword: {
    name: window.i18n.tc('字符串'),
    icon: 'icon-monitor icon-Str',
    color: '#6498B3',
    bgColor: '#D9E5EB',
  },
  text: {
    name: window.i18n.tc('文本'),
    icon: 'icon-monitor icon-text1',
    color: '#508CC8',
    bgColor: '#E1E7F2',
  },
  date: {
    name: window.i18n.tc('时间'),
    icon: 'icon-monitor icon-Time',
    color: '#CDAE71',
    bgColor: '#EDE7DB',
  },
};

export interface IValue {
  id: string;
  name: string;
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
  search?: string;
  field?: string;
}
export interface IOptionsInfo {
  count: 0;
  list: IValue[];
}
export type TGetValueFn = (params: IGetValueFnParams) => Promise<IOptionsInfo>;

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

export interface IFieldItem {
  /* 字段名 */
  field: string;
  /* 字段别名 */
  alias: string;
  /* 是否含有可选项选项 */
  isEnableOptions: boolean;
  /* 包含的method */
  methods: IValue[];
  type?: EFieldType;
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
    type: String,
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
    type: String,
    default: '',
  },
  dataId: {
    type: String,
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
    type: Boolean,
    default: false,
  },
  defaultShowResidentBtn: {
    type: Boolean,
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
    type: String,
    default: '',
  },
};
export const UI_SELECTOR_EMITS = {
  change: (_v: IFilterItem[]) => {},
} as const;
export const UI_SELECTOR_OPTIONS_PROPS = {
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
    type: Object as PropType<IFilterItem>,
    default: () => null,
  },
  show: {
    type: Boolean,
    default: false,
  },
  keyword: {
    type: String,
    default: '',
  },
};
export const UI_SELECTOR_OPTIONS_EMITS = {
  confirm: (_v: IFilterItem) => {},
  cancel: () => {},
} as const;
export const VALUE_TAG_SELECTOR_PROPS = {
  value: {
    type: Array as PropType<IValue[]>,
    default: () => [],
  },
  fieldInfo: {
    type: Object as PropType<IFieldItem>,
    default: () => null,
  },
  autoFocus: {
    type: Boolean,
    default: false,
  },
  getValueFn: {
    type: Function as PropType<TGetValueFn>,
    default: () =>
      Promise.resolve({
        count: 0,
        list: [],
      }),
  },
};
export const VALUE_TAG_SELECTOR_EMITS = {
  change: (_v: IValue[]) => {},
  dropDownChange: (_v: boolean) => {},
  selectorBlur: () => {},
  selectorFocus: () => {},
} as const;
export const AUTO_WIDTH_INPUT_PROPS = {
  value: {
    type: String,
    default: '',
  },
  fontSize: {
    type: Number,
    default: 12,
  },
  isFocus: {
    type: Boolean,
    default: false,
  },
  height: {
    type: Number,
    default: 22,
  },
  initWidth: {
    type: Number,
    default: 12,
  },
  placeholder: {
    type: String,
    default: '',
  },
};
export const AUTO_WIDTH_INPUT_EMITS = {
  focus: () => {},
  blur: () => {},
  input: (_v: string) => {},
  enter: () => {},
  backspace: () => {},
  backspaceNull: () => {},
} as const;
export const VALUE_TAG_INPUT_PROPS = {
  value: {
    type: String,
    default: '',
  },
  isOneRow: {
    type: Boolean,
    default: false,
  },
};
export const VALUE_TAG_INPUT_EMITS = {
  input: (_v: string) => {},
  change: (_v: string) => {},
  delete: (_e?: MouseEvent) => {},
};
export const VALUE_OPTIONS_PROPS = {
  selected: {
    type: Array as PropType<string[]>,
    default: () => [],
  },
  search: {
    type: String,
    default: '',
  },
  fieldInfo: {
    type: Object as PropType<IFieldItem>,
    default: () => null,
  },
  isPopover: {
    type: Boolean,
    default: false,
  },
  show: {
    type: Boolean,
    default: false,
  },
  getValueFn: {
    type: Function as PropType<TGetValueFn>,
    default: () =>
      Promise.resolve({
        count: 0,
        list: [],
      }),
  },
  width: {
    type: Number,
    default: 0,
  },
  needUpDownCheck: {
    type: Boolean,
    default: true,
  },
  noDataSimple: {
    type: Boolean,
    default: false,
  },
};
export const VALUE_OPTIONS_EMITS = {
  isChecked: (_v: boolean) => {},
  select: (_v: IValue) => {},
};
