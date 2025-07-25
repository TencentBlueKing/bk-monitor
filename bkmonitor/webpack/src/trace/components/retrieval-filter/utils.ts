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

import type { ShallowRef } from 'vue';

import { formatDuration } from './duration-input-utils';
import { type IFilterItem, type IWhereItem, ECondition, EMethod } from './typing';

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
  long: {
    name: window.i18n.t('数字'),
    icon: 'icon-monitor icon-number1',
    color: '#60A087',
    bgColor: '#DDEBE6',
  },
  boolean: {
    name: window.i18n.t('布尔'),
    icon: 'icon-monitor icon-buer',
    color: '#CB7979',
    bgColor: '#F0DFDF',
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
  other: {
    name: window.i18n.t('其他'),
    icon: 'icon-monitor icon-Others',
    color: '#B59D8D',
    bgColor: '#EBE0D9',
  },
};

export const RETRIEVAL_FILTER_UI_DATA_CACHE_KEY = '__vue3_RETRIEVAL_FILTER_UI_DATA_CACHE_KEY__';
export function defaultWhereItem(params = {}): IWhereItem {
  return {
    condition: ECondition.and,
    key: '',
    method: EMethod.eq,
    value: [],
    ...params,
  };
}
export function getCacheUIData(): IFilterItem[] {
  const uiDataSrt = localStorage.getItem(RETRIEVAL_FILTER_UI_DATA_CACHE_KEY);
  try {
    return (JSON.parse(uiDataSrt) || []).map(item => ({
      ...item,
      value: item.value.map(v => ({
        id: typeof v.id === 'object' ? JSON.stringify(v.id) : v.id,
        name: typeof v.name === 'object' ? JSON.stringify(v.name) : v.name,
      })),
    }));
  } catch (err) {
    console.log(err);
    return [];
  }
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
export function isNumeric(str) {
  return /^[-+]?(\d+(\.\d*)?|\.\d+)([eE][-+]?\d+)?$/.test(str);
}
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
        (sourceItem?.method || null) === (item?.method || null) &&
        JSON.stringify(sourceItem.value) === JSON.stringify(item.value) &&
        (sourceItem?.options?.is_wildcard || null) === (item?.options?.is_wildcard || null) &&
        (sourceItem?.options?.group_relation || null) === (item?.options?.group_relation || null) &&
        (sourceItem?.operator || null) === (item?.operator || null)
      )
    ) {
      localTarget.push(item);
    }
  }
  result = [...source, ...localTarget];
  return result;
}

export function onClickOutside(element, callback, { once = false } = {}) {
  const handler = (event: MouseEvent) => {
    let isInside = false;
    if (Array.isArray(element)) {
      isInside = element.some(el => !!el?.contains?.(event.target));
    } else {
      isInside = element.contains(event.target);
    }
    if (!isInside) {
      callback(event);
      if (once) window.removeEventListener('click', handler);
    }
  };
  window.addEventListener('click', handler);
  return () => window.removeEventListener('click', handler);
}

/**
 * @description 缓存ui数据
 * @param v
 */
export function setCacheUIData(v: IFilterItem[]) {
  localStorage.setItem(RETRIEVAL_FILTER_UI_DATA_CACHE_KEY, JSON.stringify(v));
}

export const TIME_CONSUMING_REGEXP = /^([1-9][0-9]*|0)(\.[0-9]*[1-9])?(ns|μs|ms|s|m|h|d)$/;

export const traceWhereFormatter = (where: IWhereItem[]) => {
  return where.map(item => ({
    key: item.key,
    method: item?.operator || item?.method || '',
    value: item.value,
    condition: ECondition.and,
    options: item?.options || {},
  })) as IWhereItem[];
};
export const equalWhere = (source: IWhereItem[], target: IWhereItem[]) => {
  let result = true;
  let index = -1;
  if (target.length !== source.length) {
    return false;
  }
  for (const s of source) {
    index += 1;
    const sItem = s;
    const tItem = target[index];
    if (!tItem) {
      result = false;
      break;
    }
    if (
      !(
        sItem?.key === tItem?.key &&
        sItem?.method === tItem?.method &&
        sItem?.operator === tItem?.operator &&
        sItem?.options?.is_wildcard === tItem?.options?.is_wildcard &&
        sItem?.options?.group_relation === tItem?.options?.group_relation &&
        JSON.stringify(sItem?.value || []) === JSON.stringify(tItem?.value || [])
      )
    ) {
      result = false;
      break;
    }
  }
  return result;
};

export const DURATION_KEYS = ['trace_duration', 'elapsed_time'];
export const TRACE_DEFAULT_RESIDENT_SETTING_KEY = [
  'trace_id',
  'trace_duration',
  'resource.service.name',
  'collections.resource.service.name',
  'span_name',
  'collections.span_name',
];
export const SPAN_DEFAULT_RESIDENT_SETTING_KEY = ['trace_id', 'elapsed_time', 'resource.service.name', 'span_name'];
export const INPUT_TAG_KEYS = ['span_id', 'trace_id'];

export function getDurationDisplay(value: Array<number | string>) {
  const str = value.map(v => (v ? `${formatDuration(Number(v))}` : '0ms')).join('~');
  return str;
}

export function getTopDocument(node = document) {
  let currentRoot = node.getRootNode();
  let nodeTemp: any = node;
  // 递归穿透 Shadow Host
  while (currentRoot !== document) {
    // 如果当前根是 Shadow Root，则向上找到宿主元素（Shadow Host）
    if (currentRoot instanceof ShadowRoot) {
      nodeTemp = currentRoot.host;
      currentRoot = nodeTemp.getRootNode();
    } else {
      break;
    }
  }
  // 返回最终的顶层 document
  return currentRoot === document ? document : currentRoot;
}
export function triggerShallowRef<T>(shallowRef: ShallowRef<T>) {
  shallowRef.value = structuredClone(shallowRef.value);
}

/* 通配符字段key */
export const WILDCARD_KEY = 'is_wildcard';
/* 组件关系字段key */
export const GROUP_RELATION_KEY = 'group_relation';
/* 存在/不存在的key */
export const EXISTS_KEYS = ['exists', 'not exists'];
/* 不需要显示值选择的操作符 */
export const NOT_VALUE_METHODS = ['exists', 'not exists'];
/* 默认组件关系 */
export const DEFAULT_GROUP_RELATION = 'OR';
/* 空值的id和name */
export const NULL_VALUE_NAME = `- ${window.i18n.t('空')} -`;
export const NULL_VALUE_ID = '';
/* Span 不支持弹出枚举值的字段 */
export const SPAN_NOT_SUPPORT_ENUM_KEYS = ['time', 'start_time', 'end_time', 'parent_span_id', 'span_id', 'trace_id'];
/* Trace 不支持弹出枚举值的字段 */
export const TRACE_NOT_SUPPORT_ENUM_KEYS = ['min_start_time', 'max_end_time', 'trace_id', 'root_span_id'];
