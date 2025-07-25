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
import { NULL_VALUE_ID, NULL_VALUE_NAME } from './utils';

type ICandidateValueMap = Map<
  string,
  {
    count: number;
    isEnd: boolean;
    values: { id: string; name: string }[];
  }
>;
interface IParams {
  app_name: string;
  fields: string[];
  filters: any[];
  isInit__?: boolean; // 此字段判断是否需要初始化缓存候选值，不传给接口参数
  limit: number;
  mode: string;
  query_string: string;
}
interface IRes {
  count: number;
  list: { id: string; name: string }[];
}

function getBooleanValues() {
  return JSON.parse(
    JSON.stringify([
      {
        id: 'true',
        name: 'true',
      },
      {
        id: 'false',
        name: 'false',
      },
    ])
  );
}

function getNullValue() {
  return JSON.parse(
    JSON.stringify({
      id: NULL_VALUE_ID,
      name: NULL_VALUE_NAME,
    })
  );
}

export const useCandidateValue = () => {
  let candidateValueMap: ICandidateValueMap = new Map();
  let axiosController = new AbortController();

  /* 缓存条件: 
    第一次调用接口时已获取到全部数据.
    同时只能缓存一个字段的候选值.
    参数：limit = 200(先按200条查，后续测试下查询的速度看要不要调大)
    1.-> 返回数量 >= limit， 用户后续输入检索值通过 API 模糊检索(unify - query查指标返回的数据可能会大于limit, 这里后台没做截断 
    2.-> 返回数量 < limit， 用户输入检索值由前端模糊检索（查询的数据量小于limit,检索值下拉框没有失焦用户继续输入检索值走前端的模糊检索）
    3.-> 来回切换字段、 检索值下拉框失焦再次点击，都要重新拉取候选项
  */
  function getFieldsOptionValuesProxy(
    params: IParams,
    fields: Array<{ [key: string]: any; type: string }>
  ): Promise<IRes> {
    return new Promise((resolve, _reject) => {
      if (params?.isInit__) {
        candidateValueMap = new Map();
      }
      const field = params?.fields?.[0];
      const fieldType = fields?.find(item => item?.name === field)?.type || '';
      const isKeyword = fieldType === 'keyword';
      const isBoolean = fieldType === 'boolean';
      const isNumber = ['integer', 'long'].includes(fieldType);
      const searchValue = String(params.filters?.[0]?.value?.[0] || '');
      const searchValueLower = searchValue.toLocaleLowerCase();
      const candidateItem = candidateValueMap.get(getMapKey(params));
      // const hasData = candidateItem?.values?.length >= params.limit || candidateItem?.isEnd;
      // if (searchValue ? candidateItem?.isEnd : hasData && !params?.query_string) {
      if (isBoolean) {
        const list = getBooleanValues().filter(item => item.name.includes(searchValueLower));
        resolve({
          count: list.length,
          list,
        });
      } else if (candidateItem?.isEnd && !params?.query_string) {
        if (searchValue) {
          const filterValues = candidateItem.values.filter(item => {
            const idLower = `${item.id}`.toLocaleLowerCase();
            const nameLower = item.name.toLocaleLowerCase();
            return idLower.includes(searchValueLower) || nameLower.includes(searchValueLower);
          });
          resolve({
            count: filterValues.length,
            list: isKeyword ? [getNullValue(), ...filterValues] : filterValues,
          });
        } else {
          const list = candidateItem.values.slice(0, params.limit);
          resolve({
            count: list.length,
            list: isKeyword ? [getNullValue(), ...list] : list,
          });
        }
      } else {
        axiosController.abort();
        axiosController = new AbortController();
        const paramsValue = structuredClone(params);
        if (isNumber && paramsValue?.filters?.length && paramsValue?.filters?.[0]?.operator) {
          paramsValue.filters[0].operator = 'equal';
        }
        getFieldsOptionValues(
          {
            ...paramsValue,
            isInit__: undefined,
          },
          {
            signal: axiosController.signal,
            needMessage: false,
          }
        )
          .then(res => {
            const data = res?.[params?.fields?.[0]] || [];
            const values =
              data
                .filter(item => (typeof item === 'string' ? !!item : true))
                ?.map(item => ({
                  id: item,
                  name: transformFieldName(params?.fields?.[0], item) || item,
                })) || [];
            const isEnd = values.length < params.limit;
            const newMap = new Map();

            if (!searchValue && isEnd) {
              newMap.set(getMapKey(params), {
                values: values,
                isEnd: isEnd,
                count: data.length,
              });
            }
            candidateValueMap = newMap;
            resolve({
              list: isKeyword ? [getNullValue(), ...values] : values,
              count: data.length,
            });
          })
          .catch(err => {
            if (err?.message !== 'canceled') {
              resolve({
                count: 0,
                list: isKeyword ? [getNullValue()] : [],
              });
            }
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
