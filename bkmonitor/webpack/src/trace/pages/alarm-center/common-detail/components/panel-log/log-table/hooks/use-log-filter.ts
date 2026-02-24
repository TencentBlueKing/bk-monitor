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

import { request } from 'monitor-api/base';

import type { IGetValueFnParams } from 'trace/components/retrieval-filter/typing';

export const getAggTermsData = request('POST' as any, 'apm_log_forward/bklog/api/v1/search/index_set/{pk}/aggs/terms/');

type ICandidateValueMap = Map<
  string,
  {
    count: number;
    isEnd: boolean;
    values: { id: string; name: string }[];
  }
>;

export function useLogFilter() {
  let axiosController = new AbortController();
  let candidateValueMap: ICandidateValueMap = new Map();

  let commonParams: any = {};

  function getFieldsOptionValuesProxy(params: IGetValueFnParams) {
    console.log(params);
    function getMapKey(params: IGetValueFnParams) {
      return `____${params.fields.join('')}____`;
    }

    return new Promise(resolve => {
      const searchValue = String(params.where?.[0]?.value?.[0] || '');
      const searchValueLower = searchValue.toLocaleLowerCase();
      const candidateItem = candidateValueMap.get(getMapKey(params));
      if (candidateItem?.isEnd && !params?.queryString) {
        if (searchValue) {
          const filterValues = candidateItem.values.filter(item => {
            const idLower = `${item.id}`.toLocaleLowerCase();
            const nameLower = item.name.toLocaleLowerCase();
            return idLower.includes(searchValueLower) || nameLower.includes(searchValueLower);
          });
          resolve({
            count: filterValues.length,
            list: filterValues,
          });
        } else {
          const list = candidateItem.values.slice(0, params.limit);
          resolve({
            count: list.length,
            list: list,
          });
        }
      } else {
        axiosController.abort();
        axiosController = new AbortController();
        getAggTermsData(
          commonParams.index_set_id,
          {
            end_time: commonParams.end_time,
            start_time: commonParams.start_time,
            fields: params?.fields,
            keyword: '*',
            size: (candidateItem?.count || 0) + params.limit,
          },
          {
            signal: axiosController.signal,
            needMessage: false,
          }
        )
          .then(res => {
            const values =
              res?.aggs_items?.[params?.fields?.[0]]?.map(v => ({
                id: v,
                name: v,
              })) || [];
            const isEnd = values.length < params.limit;
            const newMap = new Map();

            newMap.set(getMapKey(params), {
              values: values,
              count: values.length,
              isEnd,
            });
            candidateValueMap = newMap;
            resolve({
              list: values,
              count: values.length,
            });
          })
          .catch(err => {
            if (err?.message !== 'canceled') {
              resolve({
                count: 0,
                list: [],
              });
            }
          });
      }
    }) as any;
  }

  function setParams(newParams: any) {
    commonParams = newParams;
  }

  return {
    getFieldsOptionValuesProxy,
    setParams,
  };
}
