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

import { computed } from 'vue';

import { tryURLDecodeParse } from 'monitor-common/utils';
import { useRoute, useRouter } from 'vue-router';

import { HOST_FILTER_FIELDS, NUMBER_METHODS } from '../constants/host-list';
import { EFieldType } from '@/components/retrieval-filter/typing';
import { useHostStore } from '@/store/modules/host';

import type { EHostQuickCategory } from '../types/host-list';
export const useHostUrlParams = () => {
  const hostStore = useHostStore();

  const router = useRouter();
  const route = useRoute();

  const urlParams = computed(() => {
    return {
      where: encodeURIComponent(JSON.stringify(hostStore.where)),
      filterExpanded: String(hostStore.filterExpanded),
      activeCategory: hostStore.activeCategory,
      keyword: hostStore.keyword,
      from: hostStore.timeRange[0],
      to: hostStore.timeRange[1],
      timezone: hostStore.timezone,
      refreshInterval: hostStore.refreshInterval.toString(),
    };
  });

  function setUrlParams(otherParams: Record<string, unknown> = {}) {
    const queryParams = {
      ...route.query,
      ...urlParams.value,
      ...otherParams,
    };
    const targetRoute = router.resolve({
      query: queryParams,
    });
    /** 防止出现跳转当前地址导致报错 */
    if (targetRoute.fullPath !== route.fullPath) {
      router.replace({
        query: queryParams,
      });
    }
  }

  /**
   * 从 URL query 参数恢复主机列表过滤状态到 store
   *
   * 支持两种 URL 格式：
   * 1. 新版格式：where 参数（JSON 编码的 IWhereItem[]）
   * 2. 旧版格式：search 参数（旧版搜索条件），自动转换为 where 格式以保持向后兼容
   *
   * 同时支持 panelKey → activeCategory 的映射兼容（旧版面板 key 到新版快捷分类）
   */
  function getUrlParams() {
    const {
      where,
      filterExpanded,
      activeCategory,
      panelKey,
      queryString,
      keyword,
      from,
      to,
      timezone,
      refreshInterval,
      search,
    } = route.query;
    if (where) {
      hostStore.where = tryURLDecodeParse(where as string, []);
    } else {
      // 兼容旧版本
      const keyWordFields = HOST_FILTER_FIELDS.filter(f => f.type === EFieldType.keyword).map(f => f.name);
      const textFields = HOST_FILTER_FIELDS.filter(f => f.type === EFieldType.text).map(f => f.name);
      const numberInputFields = HOST_FILTER_FIELDS.filter(f => f.type === EFieldType.numberInput).map(f => f.name);
      const searchWhere = tryURLDecodeParse(search as string, []);
      const newWhere = [];
      for (const w of searchWhere) {
        if ([...textFields, ...keyWordFields].includes(w.id)) {
          newWhere.push({
            key: w.id,
            condition: 'and',
            value: typeof w.value === 'string' ? [w.value] : w.value,
            method: textFields.includes(w.id) ? 'include' : 'eq',
          });
        } else if (numberInputFields.includes(w.id)) {
          for (const v of w.value) {
            newWhere.push({
              key: w.id,
              condition: 'and',
              value: typeof v.value === 'string' ? [v.value] : v.value,
              method: NUMBER_METHODS.find(m => m.alias === v.condition)?.value || 'eq',
            });
          }
        } else if (w.id === 'cluster_module') {
          newWhere.push({
            key: w.id,
            condition: 'and',
            value: w.value.map(v => JSON.stringify(v)),
            method: 'eq',
          });
        } else {
          newWhere.push({
            key: w.id,
            condition: 'and',
            value: typeof w.value === 'string' ? [w.value] : w.value,
            method: 'eq',
          });
        }
      }
      hostStore.where = newWhere;
    }
    hostStore.keyword = (keyword || queryString || '') as string;
    hostStore.filterExpanded = filterExpanded === 'true' || !!hostStore.where.length;
    // 兼容旧版本面板key
    const panelKeyMap = {
      unresolveData: 'alarm',
      cpuData: 'cpu',
      menmoryData: 'mem',
      diskData: 'disk',
    };
    hostStore.activeCategory = (activeCategory || panelKeyMap?.[panelKey as string] || '') as '' | EHostQuickCategory;
    hostStore.timeRange = from && to ? [from as string, to as string] : ['now-7d', 'now'];
    hostStore.timezone = (timezone as string) || window.timezone;
    hostStore.refreshInterval = parseInt(refreshInterval as string, 10) || -1;
  }

  return {
    urlParams,
    setUrlParams,
    getUrlParams,
  };
};
