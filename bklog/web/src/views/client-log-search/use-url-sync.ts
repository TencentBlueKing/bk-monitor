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

import { useRoute, useRouter } from 'vue-router/composables';

import type { UrlState } from './types';

/** URL 条件参数的 key 列表 */
const URL_PARAM_KEYS = ['keyword', 'startTime', 'endTime', 'timezone', 'valueType', 'fileName', 'fileId', 'filterKey', 'filterType', 'highlightList'];

/** 将 URL query 中的值解析为字符串数组（单值包装为数组） */
const parseQueryArray = (
  value: string | (string | null)[] | null | undefined,
): string[] => {
  if (value === null || value === undefined) return [];
  return (Array.isArray(value) ? value : [value])
    .filter((item): item is string => item !== null && item !== undefined)
    .map(String);
};

/**
 * 客户端日志检索页面 - URL 参数同步 composable
 * 负责从 URL 读取/回填搜索条件，以及在特定操作点同步条件到 URL
 */
export default () => {
  const router = useRouter();
  const route = useRoute();

  /** 从 URL 读取初始状态 */
  const getUrlState = (): Partial<UrlState> => {
    const query = route.query;
    const state: Partial<UrlState> = {};
    if (query.keyword) state.keyword = String(query.keyword);
    if (query.startTime) state.startTime = String(query.startTime);
    if (query.endTime) state.endTime = String(query.endTime);
    if (query.timezone) state.timezone = String(query.timezone);
    if (query.fileName) state.fileName = String(query.fileName);
    if (query.fileId) state.fileId = String(query.fileId);
    if (query.filterKey) state.filterKey = parseQueryArray(query.filterKey);
    if (query.filterType) state.filterType = String(query.filterType);
    if (query.highlightList) state.highlightList = parseQueryArray(query.highlightList);
    if (query.valueType) state.valueType = String(query.valueType) as UrlState['valueType'];
    return state;
  };

  /** 将部分状态同步到 URL（合并，不覆盖其他参数） */
  const syncUrlParams = (newParams: Partial<UrlState>) => {
    const merged: Record<string, any> = { ...route.query, ...newParams };

    // 值为空则删除对应 key（undefined / null / '' / [] 都表示清除该参数）
    Object.keys(merged).forEach((key) => {
      const val = merged[key];
      if (val === undefined || val === null || val === '' || (Array.isArray(val) && val.length === 0)) {
        delete merged[key];
      }
    });

    // 如果没有 filterKey，移除 filterType
    if (!merged.filterKey) {
      delete merged.filterType;
    }

    router.replace({ query: merged });
  };

  /** 清空 URL 中的搜索条件参数 */
  const clearUrlParams = () => {
    const currentQuery = { ...route.query };
    URL_PARAM_KEYS.forEach((key) => {
      delete currentQuery[key];
    });
    router.replace({ query: currentQuery });
  };

  return {
    getUrlState,
    syncUrlParams,
    clearUrlParams,
  };
};
