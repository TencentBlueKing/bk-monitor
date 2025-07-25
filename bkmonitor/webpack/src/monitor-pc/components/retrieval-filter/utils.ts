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

export enum ECondition {
  and = 'and',
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
export enum EMode {
  queryString = 'queryString',
  ui = 'ui',
}

export const OPPOSE_METHODS = [EMethod.ne, EMethod.exclude];

export const METHOD_MAP = {
  [EMethod.eq]: '=',
  [EMethod.exclude]: window.i18n.t('不包含'),
  [EMethod.include]: window.i18n.t('包含'),
  [EMethod.ne]: '!=',
};

export const fieldTypeMap = {
  all: {
    name: window.i18n.t('数字'),
    icon: 'icon-monitor icon-a-',
    color: '#979BA5',
    bgColor: '#E8EAF0',
  },
  integer: {
    name: window.i18n.t('数字'),
    icon: 'icon-monitor icon-number1',
    color: '#60A087',
    bgColor: '#DDEBE6',
  },
  keyword: {
    name: window.i18n.t('字符串'),
    icon: 'icon-monitor icon-Str',
    color: '#6498B3',
    bgColor: '#D9E5EB',
  },
  text: {
    name: window.i18n.t('文本'),
    icon: 'icon-monitor icon-text1',
    color: '#508CC8',
    bgColor: '#E1E7F2',
  },
  date: {
    name: window.i18n.t('时间'),
    icon: 'icon-monitor icon-Time',
    color: '#CDAE71',
    bgColor: '#EDE7DB',
  },
};

/* 可选数据格式 */
export interface IFilterField {
  alias: string;
  is_dimensions?: boolean;
  is_option_enabled: boolean; // 是否可自定选项
  name: string;
  type: EFieldType;
  supported_operations: {
    alias: string;
    options?: {
      label: string;
      name: string;
    };
    value: EMethod;
  }[]; // 支持的操作
}
/* 条件结果数据格式 */
export interface IFilterItem {
  condition: { id: ECondition; name: string };
  hide?: boolean;
  isSetting?: boolean; // 是否是设置项
  key: { id: string; name: string };
  method: { id: EMethod; name: string };
  value: { id: string; name: string }[];
  options?: {
    is_wildcard: boolean;
  };
}
/* 接口where参数格式 */
export interface IWhereItem {
  condition: ECondition;
  key: string;
  method: EMethod | string;
  value: string[];
  options?: {
    is_wildcard: boolean;
  };
}
export const MODE_LIST = [
  { id: EMode.ui, name: window.i18n.t('UI 模式') },
  { id: EMode.queryString, name: window.i18n.t('语句模式') },
];

export interface IFavoriteListItem {
  id: string;
  name: string;
  favorites: {
    config: {
      queryConfig: {
        query_string: string;
        where: IWhereItem[];
      };
    };
    name: string;
  }[];
}
export interface IGetValueFnParams {
  fields?: string[];
  limit?: number;
  queryString?: string;
  where?: IWhereItem[];
}

export interface IWhereValueOptionsItem {
  count: number;
  list: {
    id: string;
    name: string;
  }[];
}

export function defaultWhereItem(params = {}): IWhereItem {
  return {
    condition: ECondition.and,
    key: '',
    method: EMethod.eq,
    value: [],
    ...params,
  };
}

/**
 * 获取字符长度，汉字两个字节
 * @param str 需要计算长度的字符
 * @returns 字符长度
 */
export function getCharLength(str) {
  const len = str.length;
  let bitLen = 0;

  for (let i = 0; i < len; i++) {
    if ((str.charCodeAt(i) & 0xff00) !== 0) {
      bitLen += 1;
    }
    bitLen += 1;
  }
  return bitLen;
}

export function getTitleAndSubtitle(str) {
  const regex = /^(.*?)（(.*?)）$/;
  const match = str.match(regex);
  return {
    title: match?.[1] || str,
    subtitle: match?.[2],
  };
}

export const RETRIEVAL_FILTER_UI_DATA_CACHE_KEY = '__RETRIEVAL_FILTER_UI_DATA_CACHE_KEY__';
interface IResidentSetting {
  field: IFilterField;
  value: IWhereItem;
}
export function getCacheUIData(): IFilterItem[] {
  const uiDataSrt = localStorage.getItem(RETRIEVAL_FILTER_UI_DATA_CACHE_KEY);
  try {
    return JSON.parse(uiDataSrt) || [];
  } catch (err) {
    console.log(err);
    return [];
  }
}

/**
 * @description 缓存ui数据
 * @param v
 */
export function setCacheUIData(v: IFilterItem[]) {
  localStorage.setItem(RETRIEVAL_FILTER_UI_DATA_CACHE_KEY, JSON.stringify(v));
}
export const RETRIEVAL_FILTER_RESIDENT_SETTING_KEY = 'RETRIEVAL_FILTER_RESIDENT_SETTING_KEY';
export enum EQueryStringTokenType {
  bracket = 'bracket',
  condition = 'condition',
  key = 'key',
  method = 'method',
  split = 'split',
  value = 'value',
  valueCondition = 'value-condition',
}
export function getResidentSettingData(): IResidentSetting[] {
  const uiDataSrt = localStorage.getItem(RETRIEVAL_FILTER_RESIDENT_SETTING_KEY);
  try {
    return JSON.parse(uiDataSrt) || [];
  } catch (err) {
    console.log(err);
    return [];
  }
}

export function isNumeric(str) {
  return /^[-+]?(\d+(\.\d*)?|\.\d+)([eE][-+]?\d+)?$/.test(str);
}
// 单次触发示例
// const removeListener = onClickOutside(targetElement, closeModal, { once: true });

/**
 * @description 合并where条件 （不相同的条件往后添加）
 * @param source
 * @param target
 * @returns
 */
export function mergeWhereList(source: IWhereItem[], target: IWhereItem[]) {
  let result: IWhereItem[] = [];
  const sourceMap: Map<string, IWhereItem> = new Map();
  for (const item of source) {
    sourceMap.set(item.key, item);
  }
  const localTarget = [];
  for (const item of target) {
    const sourceItem = sourceMap.get(item.key);
    if (
      !(
        sourceItem &&
        sourceItem.key === item.key &&
        sourceItem.method === item.method &&
        JSON.stringify(sourceItem.value) === JSON.stringify(item.value) &&
        sourceItem?.options?.is_wildcard === item?.options?.is_wildcard
      )
    ) {
      localTarget.push(item);
    }
  }
  result = [...source, ...localTarget];
  return result;
}
/**
 * @description 关闭模态框事件
 * @param element
 * @param callback
 * @param param2
 * @returns
 */
export function onClickOutside(element, callback, { once = false } = {}) {
  const handler = (event: MouseEvent) => {
    let isInside = false;
    if (Array.isArray(element)) {
      isInside = element.some(el => el.contains(event.target));
    } else {
      isInside = element.contains(event.target);
    }
    if (!isInside) {
      callback(event);
      if (once) document.removeEventListener('click', handler);
    }
  };
  document.addEventListener('click', handler);
  return () => document.removeEventListener('click', handler);
}

export function setResidentSettingData(v: IResidentSetting[]) {
  localStorage.setItem(RETRIEVAL_FILTER_RESIDENT_SETTING_KEY, JSON.stringify(v));
}

/**
 * @description 格式化where条件，调整一些不支持的的连接符
 * @param where
 * @returns
 */
export function whereFormatter(where: IWhereItem[]) {
  const result: IWhereItem[] = [];
  const methods = Object.entries(METHOD_MAP);
  const methodNames = methods.map(item => item[1]);
  for (const item of where) {
    let method = item.method;
    if (methodNames.includes(item.method)) {
      method = methods.find(m => m[1] === item.method)[0];
    }
    result.push({
      ...item,
      method,
    });
  }
  return result;
}
