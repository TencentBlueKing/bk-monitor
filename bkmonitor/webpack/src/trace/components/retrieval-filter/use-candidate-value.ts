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

import { getFieldsOptionValues } from 'monitor-api/modules/apm_trace';

import { transformFieldName } from '../../pages/trace-explore/components/trace-explore-table/constants';

type ICandidateValueMap = Map<
  string,
  {
    values: { id: string; name: string }[];
    isEnd: boolean;
  }
>;
interface IParams {
  app_name: string;
  mode: string;
  filters: any[];
  limit: number;
  fields: string[];
  query_string: string;
}
export const useCandidateValue = () => {
  let candidateValueMap: ICandidateValueMap = new Map();
  let axiosController = new AbortController();

  /* 缓存条件: 
    第一次调用接口时已获取到全部数据.
    同时只能缓存一个字段的候选值.
  */
  function getFieldsOptionValuesProxy(params: IParams): Promise<{ id: string; name: string }[]> {
    return new Promise((resolve, _reject) => {
      const candidateItem = candidateValueMap.get(getMapKey(params));
      const searchValue = String(params.filters?.[0]?.value?.[0] || '');
      const searchValueLower = searchValue.toLocaleLowerCase();
      // const hasData = candidateItem?.values?.length >= params.limit || candidateItem?.isEnd;
      // if (searchValue ? candidateItem?.isEnd : hasData && !params?.query_string) {
      if (candidateItem?.isEnd && !params?.query_string) {
        if (searchValue) {
          const filterValues = candidateItem.values.filter(item => {
            const idLower = `${item.id}`.toLocaleLowerCase();
            const nameLower = item.name.toLocaleLowerCase();
            return idLower.includes(searchValueLower) || nameLower.includes(searchValueLower);
          });
          resolve(filterValues);
        } else {
          resolve(candidateItem.values.slice(0, params.limit));
        }
      } else {
        axiosController.abort();
        axiosController = new AbortController();
        getFieldsOptionValues(params, {
          signal: axiosController.signal,
        })
          .then(res => {
            const data = res?.[params?.fields?.[0]] || [];
            const values =
              data?.map(item => ({
                id: item,
                name: transformFieldName(params?.fields?.[0], item) || '',
              })) || [];
            const isEnd = values.length < params.limit;
            if (!searchValue && isEnd) {
              const newMap = new Map();
              newMap.set(getMapKey(params), {
                values,
                isEnd: isEnd,
              });
              candidateValueMap = newMap;
            }
            resolve(values);
          })
          .catch(() => {
            resolve([]);
          });
      }
    });
  }

  function getMapKey(params: IParams) {
    return `${params.app_name}____${params.mode}____${params.fields.join('')}____`;
  }
  return {
    getFieldsOptionValuesProxy,
  };
};
