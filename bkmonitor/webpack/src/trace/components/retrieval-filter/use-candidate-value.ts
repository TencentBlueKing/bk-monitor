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
type ICandidateValueMap = Map<
  string,
  {
    values: { id: string; name: string }[];
    isEnd: boolean;
    limit: number;
  }
>;
interface IParams {
  app_name: string;
  mode: string;
  filters: any[];
  limit: number;
  fields: string[];
}
export const useCandidateValue = (axiosController: AbortController) => {
  const candidateValueMap: ICandidateValueMap = new Map();

  function getFieldsOptionValuesProxy(params: IParams): Promise<{ id: string; name: string }[]> {
    return new Promise((resolve, _reject) => {
      const candidateItem = candidateValueMap.get(getMapKey(params));
      const searchValue = String(params.filters?.[0]?.value?.[0] || '');
      const searchValueLower = searchValue.toLocaleLowerCase();
      const hasData = candidateItem?.values?.length >= params.limit || candidateItem?.isEnd;
      if (searchValue ? candidateItem?.isEnd : hasData) {
        if (searchValue) {
          const filterValues = candidateItem.values.filter(item => {
            const idLower = `${item.id}`.toLocaleLowerCase();
            // const nameLower = item.name.toLocaleLowerCase();
            return idLower.includes(searchValueLower);
          });
          resolve(filterValues);
        } else {
          resolve(candidateItem.values.slice(0, params.limit));
        }
      } else {
        getFieldsOptionValues(params, {
          signal: axiosController.signal,
        })
          .then(res => {
            const data = res?.[params?.fields?.[0]] || [];
            const values =
              data?.map(item => ({
                id: item,
                name: item,
              })) || [];
            if (!searchValue) {
              candidateValueMap.set(getMapKey(params), {
                values,
                isEnd: values.length < params.limit,
                limit: params.limit,
              });
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
