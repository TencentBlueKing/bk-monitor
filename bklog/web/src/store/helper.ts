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
export const isFeatureToggleOn = (key: string, value: string | string[]) => {
  const featureToggle = window.FEATURE_TOGGLE?.[key];
  if (featureToggle === 'debug') {
    const whiteList = (window.FEATURE_TOGGLE_WHITE_LIST?.[key] ?? []).map(id => `${id}`);

    if (Array.isArray(value)) {
      return value.some(v => whiteList.includes(v));
    }

    return whiteList.includes(value);
  }

  return featureToggle === 'on';
};

export const SESSION_STORAGE_KEY = 'CommonFilterAddition';

export type FilterAdditionStorageItem = {
  indexSetIdList: string[];
  filterAddition: Record<string, any>[];
  t: number; // ISO 8601 format timestamp
};

export type OldFilterAdditionStorageItem = {
  indexId: string;
  value: Record<string, any>[];
};

export const isAiAssistantActive = (val: string[]) => {
  return isFeatureToggleOn('ai_assistant', val);
};

export const getStorageCommonFilterAddition = () => {
  const value = sessionStorage.getItem(SESSION_STORAGE_KEY);
  let jsonValue: FilterAdditionStorageItem[] | OldFilterAdditionStorageItem = [];
  try {
    jsonValue = JSON.parse(value || '[]');

    if (!Array.isArray(jsonValue) && 'indexId' in jsonValue && 'value' in jsonValue) {
      jsonValue = [{ indexSetIdList: [jsonValue.indexId], filterAddition: [jsonValue.value], t: new Date().getTime() }];
    }
  } catch (e) {
    console.error('Failed to parse common filter addition:', e);
  }

  return jsonValue as FilterAdditionStorageItem[];
};

export const filterCommontAdditionByIndexSetId = (indexSetIdList: string[], list?: FilterAdditionStorageItem[]) => {
  let jsonValue: FilterAdditionStorageItem[] = list ?? getStorageCommonFilterAddition();
  const formatList = indexSetIdList.map(id => `${id}`);
  return jsonValue?.find(
    item =>
      item.indexSetIdList.length === formatList.length && item.indexSetIdList.every(id => formatList.includes(`${id}`)),
  );
};

/**
 * 获取常驻字段过滤设置
 * @param store
 * @returns
 */
export const getCommonFilterFieldsList = state => {
  if (Array.isArray(state.retrieve.catchFieldCustomConfig?.filterSetting)) {
    return state.retrieve.catchFieldCustomConfig?.filterSetting ?? [];
  }

  return [];
};

export const getCommonFilterAddition = state => {
  const additionValue = filterCommontAdditionByIndexSetId(state.indexItem.ids);
  const storedValue = additionValue?.filterAddition ?? [];

  const storedCommonAddition =
    (state.retrieve.catchFieldCustomConfig.filterAddition ?? []).map(({ field, operator, value }) => ({
      field,
      operator,
      value,
    })) ?? [];

  // 合并策略优化
  return getCommonFilterFieldsList(state).map(item => {
    const storedItem = storedValue?.find(v => v.field === item.field_name);
    const storeItem = storedCommonAddition?.find(addition => addition.field === item.field_name);

    // 优先级：本地存储 > store > 默认值
    return (
      storedItem ||
      storeItem || {
        field: item.field_name || '',
        operator: item.field_operator[0]?.operator ?? '=',
        value: [],
        list: [],
      }
    );
  });
};

export const getCommonFilterAdditionWithValues = state =>
  (getCommonFilterAddition(state).filter(item => item.value?.length) ?? []).map(({ field, value, operator }) => ({
    field,
    value,
    operator,
  }));

export const setStorageCommonFilterAddition = (state, filterAddition: Record<string, any>[]) => {
  const allStorage = getStorageCommonFilterAddition();
  const currentItem: FilterAdditionStorageItem = filterCommontAdditionByIndexSetId(state.indexItem.ids, allStorage);

  if (currentItem) {
    currentItem.filterAddition = filterAddition;
    currentItem.t = new Date().getTime();
    sessionStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(allStorage));
    return;
  }

  allStorage.push({
    indexSetIdList: state.indexItem.ids.map(id => `${id}`),
    filterAddition,
    t: new Date().getTime(),
  });

  /**
   * 如果本地存储超过5条，则移除最早的一条数据
   */
  if (allStorage.length > 5) {
    allStorage.sort((a, b) => a.t - b.t);
    allStorage.shift(); // 移除最早的一条数据
  }

  sessionStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(allStorage));
};

export const clearStorageCommonFilterAddition = state => {
  const allStorage = getStorageCommonFilterAddition();
  const currentItem: FilterAdditionStorageItem = filterCommontAdditionByIndexSetId(state.indexItem.ids, allStorage);
  if (currentItem) {
    const index = allStorage.indexOf(currentItem);
    if (index > -1) {
      allStorage.splice(index, 1);
      sessionStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(allStorage));
    }
  }
};
