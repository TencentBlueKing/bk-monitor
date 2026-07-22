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
    };
  });

  function setUrlParams(otherParams: Record<string, unknown>) {
    const queryParams = {
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

  function getUrlParams() {
    const { where, filterExpanded, activeCategory, keyword } = route.query;
    hostStore.where = tryURLDecodeParse(where as string, []);
    hostStore.filterExpanded = filterExpanded === 'true';
    hostStore.activeCategory = (activeCategory || '') as '' | EHostQuickCategory;
    hostStore.keyword = (keyword || '') as string;
  }

  return {
    urlParams,
    setUrlParams,
    getUrlParams,
  };
};
