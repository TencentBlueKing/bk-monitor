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
  long = 'long',
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
  is_searched?: boolean;
  can_displayed?: boolean;
  supported_operations: {
    alias: string;
    value: EMethod;
    placeholder?: string;
    operator?: string;
    label?: string;
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
  condition?: ECondition;
  method?: EMethod | string;
  operator?: string;
  value: number[] | string[];
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

export enum EQueryStringTokenType {
  bracket = 'bracket',
  condition = 'condition',
  key = 'key',
  method = 'method',
  split = 'split',
  value = 'value',
  valueCondition = 'value-condition',
}
export const OPTIONS_METHODS = [EMethod.ne, EMethod.exclude];

export const qsSelectorOptionsDescMap = {
  ':': [
    { type: 'tag', text: window.i18n.tc('等于') },
    { type: 'text', text: window.i18n.tc('某一值') },
  ],
  ':*': [
    { type: 'tag', text: window.i18n.tc('存在') },
    { type: 'text', text: window.i18n.tc('任意形式') },
  ],
  '>': [
    { type: 'tag', text: window.i18n.tc('大于') },
    { type: 'text', text: window.i18n.tc('某一值') },
  ],
  '<': [
    { type: 'tag', text: window.i18n.tc('小于') },
    { type: 'text', text: window.i18n.tc('某一值') },
  ],
  '>=': [
    { type: 'tag', text: window.i18n.tc('大于或等于') },
    { type: 'text', text: window.i18n.tc('某一值') },
  ],
  '<=': [
    { type: 'tag', text: window.i18n.tc('小于或等于') },
    { type: 'text', text: window.i18n.tc('某一值') },
  ],
  AND: [
    { type: 'text', text: window.i18n.tc('需要') },
    { type: 'tag', text: window.i18n.tc('两个参数都') },
    { type: 'text', text: window.i18n.tc('为真') },
  ],
  OR: [
    { type: 'text', text: window.i18n.tc('需要') },
    { type: 'tag', text: window.i18n.tc('一个或多个参数') },
    { type: 'text', text: window.i18n.tc('为真') },
  ],
  'AND NOT': [
    { type: 'text', text: window.i18n.tc('需要') },
    { type: 'tag', text: window.i18n.tc('一个或多个参数') },
    { type: 'text', text: window.i18n.tc('为真') },
  ],
};

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
  isTraceRetrieval: {
    type: Boolean,
    default: true,
  },
  defaultResidentSetting: {
    type: Array as PropType<string[]>,
    default: () => [],
  },
};
export const RETRIEVAL_FILTER_EMITS = {
  favorite: (_isEdit: boolean) => true,
  whereChange: (_v: IWhereItem[]) => true,
  queryStringChange: (_v: string) => true,
  modeChange: (_v: EMode) => true,
  queryStringInputChange: (_v: string) => true,
  commonWhereChange: (_where: IWhereItem[]) => true,
  showResidentBtnChange: (_v: boolean) => true,
  search: () => true,
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
  change: (_v: IFilterItem[]) => true,
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
  confirm: (_v: IFilterItem) => true,
  cancel: () => true,
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
  placeholder: {
    type: String,
    default: '',
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
  change: (_v: IValue[]) => true,
  dropDownChange: (_v: boolean) => true,
  selectorBlur: () => true,
  selectorFocus: () => true,
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
  focus: () => true,
  blur: () => true,
  input: (_v: string) => true,
  enter: () => true,
  backspace: () => true,
  backspaceNull: () => true,
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
  input: (_v: string) => true,
  change: (_v: string) => true,
  delete: (_e?: MouseEvent) => true,
} as const;
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
  isChecked: (_v: boolean) => true,
  select: (_v: IValue) => true,
} as const;
export const QS_SELECTOR_PROPS = {
  fields: {
    type: Array as PropType<IFilterField[]>,
    default: () => [],
  },
  value: {
    type: String,
    default: '',
  },
  qsSelectorOptionsWidth: {
    type: Number,
    default: 0,
  },
  getValueFn: {
    type: Function as PropType<(params: IGetValueFnParams) => Promise<IWhereValueOptionsItem>>,
    default: () =>
      Promise.resolve({
        count: 0,
        list: [],
      }),
  },
  favoriteList: {
    type: Array as PropType<IFavoriteListItem[]>,
    default: () => [],
  },
  clearKey: {
    type: String,
    default: '',
  },
};
export const QS_SELECTOR_EMITS = {
  query: (_v?: string) => true,
  change: (_v: string) => true,
} as const;
export const QS_SELECTOR_OPTIONS_PROPS = {
  search: {
    type: String,
    default: '',
  },
  fields: {
    type: Array as PropType<IFilterField[]>,
    default: () => [],
  },
  type: {
    type: String as PropType<EQueryStringTokenType>,
    default: '',
  },
  show: {
    type: Boolean,
    default: false,
  },
  field: {
    type: String,
    default: '',
  },
  getValueFn: {
    type: Function as PropType<(params: IGetValueFnParams) => Promise<IWhereValueOptionsItem>>,
    default: () =>
      Promise.resolve({
        count: 0,
        list: [],
      }),
  },
  favoriteList: {
    type: Array as PropType<IFavoriteListItem[]>,
    default: () => [],
  },
  queryString: {
    type: String,
    default: '',
  },
};
export const QS_SELECTOR_OPTIONS_EMITS = {
  selectFavorite: (_v: string) => true,
  select: (_v: string) => true,
} as const;
export const KV_TAG_PROPS = {
  value: {
    type: Object as PropType<IFilterItem>,
    default: () => null,
  },
  active: {
    type: Boolean,
    default: false,
  },
};
export const KV_TAG_EMITS = {
  delete: () => true,
  update: (_event: MouseEvent) => true,
  hide: () => true,
} as const;
export const RESIDENT_SETTING_TRANSFER_PROPS = {
  fields: {
    type: Array as PropType<IFilterField[]>,
    default: () => [],
  },
  value: {
    type: Array as PropType<string[]>,
    default: () => [],
  },
  show: {
    type: Boolean,
    default: false,
  },
};
export const RESIDENT_SETTING_TRANSFER_EMITS = {
  confirm: (_v: IFilterField[]) => true,
  cancel: () => true,
} as const;
export const SETTING_KV_SELECTOR_PROPS = {
  fieldInfo: {
    type: Object as PropType<IFieldItem>,
    default: () => null,
  },
  value: {
    type: Object as PropType<IWhereItem>,
    default: () => null,
  },
  maxWidth: {
    type: Number,
    default: 560,
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
export const SETTING_KV_SELECTOR_EMITS = {
  change: (_v: IWhereItem) => true,
} as const;
export const RESIDENT_SETTING_PROPS = {
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
    type: Array as PropType<IWhereItem[]>,
    default: () => [],
  },
  residentSettingOnlyId: {
    type: String,
    default: '',
  },
  isDefaultSetting: {
    type: Boolean,
    default: true,
  },
  defaultResidentSetting: {
    type: Array as PropType<string[]>,
    default: () => [],
  },
};
export const RESIDENT_SETTING_EMITS = {
  change: (_v: IWhereItem[]) => true,
} as const;
export const TIME_CONSUMING_PROPS = {
  styleType: {
    type: String as PropType<'' | 'form'>,
    default: '',
  },
  value: {
    type: Array as PropType<number[] | string[]>,
    default: () => [],
  },
};
export const TIME_CONSUMING_EMITS = {
  change: (_v: number[] | string[]) => true,
} as const;
