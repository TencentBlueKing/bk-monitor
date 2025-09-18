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
import useStore from '@/hooks/use-store';
import { useRoute, useRouter } from 'vue-router/composables';

import RouteUrlResolver, { RetrieveUrlResolver } from '../../store/url-resolver';
import $http from '@/api';

import type { ConsitionItem } from '../../store/store.type';

export default () => {
  const store = useStore();
  const router = useRouter();
  const route = useRoute();

  /**
   * 用于处理
   * @param { search_mode, addition, keyword }
   * @param ignoreKeywodLength 是否忽略 keyword 长度，如果忽略，则不进行 keyword 的长度校验, 默认为 false
   * @returns
   */
  const resolveQueryParams = ({ search_mode, addition, keyword }, ignoreKeywodLength = false) => {
    // 此时说明来自旧版URL，同时带有 addition 和 keyword
    // 这种情况下需要将 addition 转换为 keyword 进行查询合并
    // 同时设置 search_mode 为 sql
    if (!search_mode && addition?.length > 0 && (ignoreKeywodLength || keyword?.length > 0)) {
      // 这里不好做同步请求，所以直接设置 search_mode 为 sql
      router.push({ query: { ...route.query, search_mode: 'sql', addition: '[]', tab: 'origin' } });
      const resolver = new RouteUrlResolver({ route, resolveFieldList: ['addition'] });
      const target = Array.isArray(addition)
        ? { addition }
        : resolver.convertQueryToStore<{ addition: ConsitionItem[] }>();

      if (target.addition?.length) {
        return $http
          .request('retrieve/generateQueryString', {
            data: {
              addition: target.addition,
            },
          })
          .then(res => {
            if (res.result) {
              let newKeyword = [keyword, res.data?.querystring]
                .filter(item => item.length > 0 && item !== '*')
                .join(' AND ');
              if (newKeyword.length === 0) {
                newKeyword = '*';
              }

              store.commit('updateIndexItemParams', { keyword: newKeyword });
              return router.replace({ query: { ...route.query, keyword: newKeyword, addition: [], tab: 'origin' } });
            }

            return Promise.resolve(true);
          });
      }
    }

    return Promise.resolve(true);
  };

  const resolveCommonParams = ({ search_mode, addition, keyword }) => {
    if (!search_mode) {
      if (keyword?.length > 0 && addition.length < 4) {
        store.commit('updateIndexItemParams', { keyword, search_mode: 'sql' });
        return router.replace({ query: { ...route.query, keyword, addition: [] } });
      }

      if (addition?.length >= 4 && keyword?.length === 0) {
        store.commit('updateIndexItemParams', { addition, search_mode: 'ui' });

        const resolver = new RetrieveUrlResolver({
          addition,
          search_mode: 'ui',
          keyword: '',
        });

        const query = route.query;
        Object.assign(query, resolver.resolveParamsToUrl());

        return router.replace({ query });
      }
    }

    return Promise.resolve(true);
  };

  return { resolveQueryParams, resolveCommonParams };
};
