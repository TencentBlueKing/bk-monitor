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

import type { IFilterItem, IWhereItem } from './typing';

export const RETRIEVAL_FILTER_UI_DATA_CACHE_KEY = '__vue3_RETRIEVAL_FILTER_UI_DATA_CACHE_KEY__';
/**
 * @description 缓存ui数据
 * @param v
 */
export function setCacheUIData(v: IFilterItem[]) {
  localStorage.setItem(RETRIEVAL_FILTER_UI_DATA_CACHE_KEY, JSON.stringify(v));
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
export function isNumeric(str) {
  return /^[-+]?(\d+(\.\d*)?|\.\d+)([eE][-+]?\d+)?$/.test(str);
}
export function getTitleAndSubtitle(str) {
  const regex = /^(.*?)（(.*?)）$/;
  const match = str.match(regex);
  return {
    title: match?.[1] || str,
    subtitle: match?.[2],
  };
}
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
