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

import {
  type IGetValueFnParams,
  type IWhereValueOptionsItem,
  EMode,
} from '../../../../../components/retrieval-filter/typing';
import { AlarmServiceFactory } from '../../../../../pages/alarm-center/services/factory';

import type { AlarmType } from '../../../../../pages/alarm-center/typings';

type ICandidateValueMap = Map<
  string,
  {
    count: number;
    isEnd: boolean;
    values: { id: string; name: string }[];
  }
>;

export function useAlarmFilter(
  options: () => { alarmType: AlarmType; commonFilterParams: Record<string, any>; filterMode: EMode }
) {
  let axiosController = new AbortController();
  let candidateValueMap: ICandidateValueMap = new Map();

  let preAlarmType = options().alarmType;

  function getRetrievalFilterValueData(params: IGetValueFnParams): Promise<IWhereValueOptionsItem> {
    if (preAlarmType !== options().alarmType) {
      candidateValueMap.clear();
      preAlarmType = options().alarmType;
    }
    return getFieldsOptionValuesProxy(params) as any;
  }

  function getFieldsOptionValuesProxy(params: IGetValueFnParams) {
    function getMapKey(params: IGetValueFnParams) {
      return `${options().alarmType}____${options().filterMode}____${params.fields.join('')}____`;
    }
    function removeQuotesIfWrapped(str) {
      // 正则表达式匹配被双引号包裹的字符串
      const regex = /^"(.*)"$/;

      // 如果匹配成功，则返回去掉一层双引号的内容
      if (regex.test(str)) {
        return str.replace(regex, '$1');
      }

      // 如果不匹配，返回原字符串
      return str;
    }
    return new Promise(resolve => {
      // if (params?.isInit__) {
      //   candidateValueMap = new Map();
      // }
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
        AlarmServiceFactory(options().alarmType)
          .getRetrievalFilterValues(
            {
              ...options().commonFilterParams,
              conditions: [],
              fields: params.fields,
              size: params.limit,
            },
            {
              signal: axiosController.signal,
              needMessage: false,
            }
          )
          .then(res => {
            const values = (res.fields?.find(f => f.field === params?.fields?.[0])?.buckets || []).map(item => {
              if (options().filterMode === EMode.ui) {
                return {
                  ...item,
                  id: removeQuotesIfWrapped(item.id),
                };
              }
              return item;
            });
            const isEnd = values.length < params.limit;
            const newMap = new Map();
            if (!searchValue && isEnd) {
              // 只在聚焦失焦是缓存
              newMap.set(getMapKey(params), {
                values: values,
                isEnd: isEnd,
                count: values.length,
              });
            }
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
    });
  }

  return {
    getRetrievalFilterValueData,
  };
}
