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

import type { PropType } from 'vue';

export enum EFieldType {
  // 全文检索输入框
  all = 'all',
  boolean = 'boolean',
  date = 'date',
  // 是否为耗时组件
  duration = 'duration',
  // input输入框
  input = 'input',
  integer = 'integer',
  keyword = 'keyword',
  long = 'long',
  // textarea 输入框
  text = 'text',
}
export enum EMethod {
  containsMatchPhrase = 'contains match phrase',
  eq = 'equal',
  exclude = 'exclude',
  exists = 'exists',
  include = 'include',
  like = 'link',
  ne = 'not_equal',
  notContainsMatchPhrase = 'not contains match phrase',
  notExists = 'not exists',
  notLike = 'not_like',
}

export enum EMode {
  queryString = 'queryString',
  ui = 'ui',
}

export const METHOD_MAP = {
  [EMethod.eq]: '=',
  [EMethod.exclude]: window.i18n.t('不包含'),
  [EMethod.include]: window.i18n.t('包含'),
  [EMethod.ne]: '!=',
};

export enum APIType {
  APM = 'apm', // apm
  MONITOR = 'monitor', // monitor default
}

export enum ECondition {
  and = 'and',
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
export interface IFavoriteListItem {
  groupName: string;
  id: string;
  name: string;
  config: {
    commonWhere?: IWhereItem[];
    queryString?: string;
    where?: IWhereItem[];
  };
}

export interface IFieldItem {
  /* 字段别名 */
  alias: string;
  /* 字段名 */
  field: string;
  /* 是否含有可选项选项 */
  isEnableOptions: boolean;
  /* 包含的method */
  methods: IValue[];
  type?: EFieldType;
}
export interface IFilterField {
  // 字段别名
  alias: string;
  // isDimensions: boolean;
  // 是否需要异步加载数据
  isEnableOptions?: boolean;
  // 字段名
  name: string;
  // 字段类型
  type: EFieldType;
  // 支持的操作符
  methods: {
    // 操作符别名
    alias: string;
    // options用于是否展示通配符或者组件关系等其他选项字段
    /* 通配符字段key */
    // const WILDCARD_KEY = 'is_wildcard';
    /* 组件关系字段key */
    // const GROUP_RELATION_KEY = 'group_relation';
    options?: {
      children?: {
        // 其他选项的可选项
        label: string; // 其他选项的可选项别名
        value: string; // 其他选项的可选项值
      }[];
      default?: boolean | string; // 其他选项字段默认值
      label: string; // 其他选项字段别名
      name: string; // 当前暂时支持WILDCARD_KEY， GROUP_RELATION_KEY
    }[];
    // 操作符显示的placeholder TODO(待支持)
    placeholder?: string;
    // 操作符id
    value: EMethod | string;
    // 用于进行异步搜索时的默认操作符
    wildcardValue?: string;
  }[];
}

export interface IFilterItem {
  condition: { id: ECondition; name: string };
  hide?: boolean;
  isSetting?: boolean; // 是否是设置项
  key: { id: string; name: string };
  method: { id: EMethod | string; name: string };
  value: { id: number | string; name: number | string }[];
  options?:
    | Record<string, any>
    | {
        group_relation?: string;
        is_wildcard?: boolean;
      };
}

export interface IGetValueFnParams {
  field?: string;
  fields?: string[];
  isInit__?: boolean; // 此字段不传给后台(在聚焦或者查询的时候此值为true)
  limit?: number;
  queryString?: string;
  search?: string;
  where?: IWhereItem[];
}

export type IHandleGetUserConfig = (key: string, config?: Record<string, any>) => Promise<string[] | undefined>;

export type IHandleSetUserConfig = (value: string, configId?: string) => Promise<boolean>;

//  组件内部标准格式
export interface INormalWhere {
  condition: ECondition;
  key: string;
  method: EMethod | string;
  value: Array<number | string>;
  options:
    | Record<string, any>
    | {
        group_relation?: boolean;
        is_wildcard?: boolean;
      };
}
export interface IOptionsInfo {
  count: 0;
  list: IValue[];
}

export interface IValue {
  id: string;
  name: string;
}

// 组件外部格式
export interface IWhereItem {
  condition?: ECondition | string;
  key: string;
  method?: EMethod | string;
  operator?: string;
  value: number[] | string[];
  options?: {
    group_relation?: boolean;
    is_wildcard?: boolean;
  };
}

export interface IWhereValueOptionsItem {
  count: number;
  list: {
    id: string;
    name: string;
  }[];
}
export type TGetValueFn = (params: IGetValueFnParams) => Promise<IOptionsInfo>;

// interface FavList {
//   config: any;
//   create_user: string;
//   disabled?: boolean;
//   group_id: number | object;
//   groupName?: string;
//   id: number;
//   name: string;
//   update_time: string;
//   update_user: string;
// }
export const NOT_TYPE_METHODS = [
  EMethod.ne,
  EMethod.exclude,
  EMethod.notExists,
  EMethod.notLike,
  EMethod.notContainsMatchPhrase,
];

export const qsSelectorOptionsDescMap = {
  ':': [
    { type: 'tag', text: window.i18n.t('等于') },
    { type: 'text', text: window.i18n.t('某一值') },
  ],
  ':*': [
    { type: 'tag', text: window.i18n.t('存在') },
    { type: 'text', text: window.i18n.t('任意形式') },
  ],
  '>': [
    { type: 'tag', text: window.i18n.t('大于') },
    { type: 'text', text: window.i18n.t('某一值') },
  ],
  '<': [
    { type: 'tag', text: window.i18n.t('小于') },
    { type: 'text', text: window.i18n.t('某一值') },
  ],
  '>=': [
    { type: 'tag', text: window.i18n.t('大于或等于') },
    { type: 'text', text: window.i18n.t('某一值') },
  ],
  '<=': [
    { type: 'tag', text: window.i18n.t('小于或等于') },
    { type: 'text', text: window.i18n.t('某一值') },
  ],
  AND: [
    { type: 'text', text: window.i18n.t('需要') },
    { type: 'tag', text: window.i18n.t('两个参数都') },
    { type: 'text', text: window.i18n.t('为真') },
  ],
  OR: [
    { type: 'text', text: window.i18n.t('需要') },
    { type: 'tag', text: window.i18n.t('一个或多个参数') },
    { type: 'text', text: window.i18n.t('为真') },
  ],
  'AND NOT': [
    { type: 'text', text: window.i18n.t('需要') },
    { type: 'tag', text: window.i18n.t('一个或多个参数') },
    { type: 'text', text: window.i18n.t('为真') },
  ],
};

export const RETRIEVAL_FILTER_PROPS = {
  // 字段列表
  fields: {
    type: Array as PropType<IFilterField[]>,
    default: () => [],
  },
  // 检索值候选项获取
  getValueFn: {
    type: Function as PropType<(params: IGetValueFnParams) => Promise<IWhereValueOptionsItem>>,
    default: () =>
      Promise.resolve({
        count: 0,
        list: [],
      }),
  },
  // ui模式数据
  where: {
    type: Array as PropType<IWhereItem[]>,
    default: () => [],
  },
  // 常驻筛选数据
  commonWhere: {
    type: Array as PropType<IWhereItem[]>,
    default: () => [],
  },
  // 语句模式数据
  queryString: {
    type: String,
    default: '',
  },
  // 当前选择收藏项
  selectFavorite: {
    type: Object as PropType<{
      commonWhere?: IWhereItem[];
      where?: IWhereItem[];
    }>,
    default: () => null,
  },
  // 收藏列表
  favoriteList: {
    type: Array as PropType<IFavoriteListItem[]>,
    default: () => [],
  },
  // 常驻设置唯一id
  residentSettingOnlyId: {
    type: String,
    default: '',
  },
  // 是否为默认常驻设置
  isDefaultResidentSetting: {
    type: Boolean,
    default: true,
  },
  // 当前模式
  filterMode: {
    type: String as PropType<EMode>,
    default: EMode.ui,
  },
  // 是否包含收藏功能
  isShowFavorite: {
    type: Boolean,
    default: false,
  },
  // 是否需要常驻设置功能
  isShowResident: {
    type: Boolean,
    default: false,
  },
  // 是否需要复制功能
  isShowCopy: {
    type: Boolean,
    default: false,
  },
  // 是否需要清空功能
  isShowClear: {
    type: Boolean,
    default: false,
  },
  // 是否需要最右侧的搜索按钮
  isShowSearchBtn: {
    type: Boolean,
    default: true,
  },
  // 当前默认是否展示常驻设置
  defaultShowResidentBtn: {
    type: Boolean,
    default: false,
  },
  // 当前默认常驻设置展示字段
  defaultResidentSetting: {
    type: Array as PropType<string[]>,
    default: () => [],
  },
  placeholder: {
    type: String,
    default: window.i18n.t('快捷键 / ，可直接输入'),
  },
  // 是否是单显示模式
  isSingleMode: {
    type: Boolean,
    default: false,
  },
  // 为了支持外部各类where条件格式可以自定义格式
  // 将自定义格式转换为组件内支持格式
  whereFormatter: {
    type: Function as PropType<(where: any[]) => INormalWhere[]>,
    default: (v: any[]) => {
      return v;
    },
  },
  // 将组件内支持格式转换为外部自定义格式
  changeWhereFormatter: {
    type: Function as PropType<(where: INormalWhere[]) => any[]>,
    default: (v: INormalWhere[]) => {
      return v;
    },
  },
  // 常驻设置获取用户配置
  handleGetUserConfig: {
    type: Function as PropType<IHandleGetUserConfig>,
    default: () => Promise.resolve(undefined),
  },
  // 常驻设置设置用户配置
  handleSetUserConfig: {
    type: Function as PropType<IHandleSetUserConfig>,
    default: () => Promise.resolve(false),
  },
  // 延迟加载（降低加载数据时的跳动）
  loadDelay: {
    type: Number,
    default: 300,
  },
  // 滚动加载时一次拉取量
  limit: {
    type: Number,
    default: 200,
  },
  // 下拉弹层z-index
  zIndex: {
    type: Number,
    default: 1000,
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
  copyWhere: (_v: IWhereItem[]) => true,
  setFavoriteCache: (_commonWhere: IWhereItem[]) => true,
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
  placeholder: {
    type: String,
    default: window.i18n.t('快捷键 / ，可直接输入'),
  },
  loadDelay: {
    type: Number,
    default: 300,
  },
  // 滚动加载时一次拉取量
  limit: {
    type: Number,
    default: 200,
  },
  // 下拉弹层z-index
  zIndex: {
    type: Number,
    default: 1000,
  },
  /** 拥有快捷键功能 */
  hasShortcutKey: {
    type: Boolean,
    default: true,
  },
  /** tag是否有隐藏功能 */
  hasTagHidden: {
    type: Boolean,
    default: true,
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
  loadDelay: {
    type: Number,
    default: 300,
  },
  // 滚动加载时一次拉取量
  limit: {
    type: Number,
    default: 200,
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
  // 延迟加载
  loadDelay: {
    type: Number,
    default: 300,
  },
  // 滚动加载时一次拉取量
  limit: {
    type: Number,
    default: 200,
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
    type: [String, Number],
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
  // 延迟加载
  loadDelay: {
    type: Number,
    default: 300,
  },
  // 滚动加载时一次拉取量
  limit: {
    type: Number,
    default: 200,
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
  placeholder: {
    type: String,
    default: window.i18n.t('快捷键 / ，可直接输入'),
  },
  // 下拉弹层z-index
  zIndex: {
    type: Number,
    default: 1000,
  },
  // 是否展示收藏功能
  isShowFavorite: {
    type: Boolean,
    default: true,
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
  // 是否展示收藏功能
  isShowFavorite: {
    type: Boolean,
    default: true,
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
  hasTagHidden: {
    type: Boolean,
    default: true,
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
    type: Object as PropType<INormalWhere>,
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
  loadDelay: {
    type: Number,
    default: 300,
  },
  // 滚动加载时一次拉取量
  limit: {
    type: Number,
    default: 200,
  },
};
export const SETTING_KV_SELECTOR_EMITS = {
  change: (_v: INormalWhere) => true,
} as const;
export const SETTING_KV_INPUT_PROPS = {
  fieldInfo: {
    type: Object as PropType<IFieldItem>,
    default: () => null,
  },
  value: {
    type: Object as PropType<INormalWhere>,
    default: () => null,
  },
  maxWidth: {
    type: Number,
    default: 560,
  },
};
export const SETTING_KV_INPUT_EMITS = {
  change: (_v: INormalWhere) => true,
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
    type: Array as PropType<INormalWhere[]>,
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
  handleGetUserConfig: {
    type: Function as PropType<IHandleGetUserConfig>,
    default: () => Promise.resolve(undefined),
  },
  handleSetUserConfig: {
    type: Function as PropType<IHandleSetUserConfig>,
    default: () => Promise.resolve(false),
  },
  loadDelay: {
    type: Number,
    default: 300,
  },
  // 滚动加载时一次拉取量
  limit: {
    type: Number,
    default: 200,
  },
};
export const RESIDENT_SETTING_EMITS = {
  change: (_v: INormalWhere[]) => true,
} as const;
export const TIME_CONSUMING_PROPS = {
  fieldInfo: {
    type: Object as PropType<IFieldItem>,
    default: () => null,
  },
  styleType: {
    type: String as PropType<'' | 'form'>,
    default: '',
  },
  value: {
    type: Object as PropType<INormalWhere>,
    default: () => null,
  },
};
export const TIME_CONSUMING_EMITS = {
  change: (_v: INormalWhere) => true,
} as const;
