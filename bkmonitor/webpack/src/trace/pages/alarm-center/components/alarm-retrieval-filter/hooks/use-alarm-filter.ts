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

import { computed, watch } from 'vue';

import { random } from 'monitor-common/utils';

import { type IGetValueFnParams, EMode } from '../../../../..//components/retrieval-filter/typing';
import { useAlarmCenterStore } from '../../../../../store/modules/alarm-center';

import type { CommonCondition } from '../../../../../pages/alarm-center/typings/services';

type ICandidateValueMap = Map<
  string,
  {
    count: number;
    isEnd: boolean;
    values: { id: string; name: string }[];
  }
>;

interface ICondition extends CommonCondition {
  condition: any | string;
}

interface IParams {
  fields: string[];
  filters: any[];
  isInit__?: boolean; // 此字段判断是否需要初始化缓存候选值，不传给接口参数
  limit: number;
  mode: string;
  query_string: string;
}

export function useAlarmFilter() {
  const alarmStore = useAlarmCenterStore();
  let axiosController = new AbortController();
  let candidateValueMap: ICandidateValueMap = new Map();

  const condition = computed(() => {
    return alarmStore.conditions as ICondition[];
  });
  const residentCondition = computed(() => {
    return alarmStore.residentCondition as ICondition[];
  });
  const queryString = computed(() => {
    return alarmStore.queryString;
  });
  const residentSettingOnlyId = computed(() => {
    return `ALARM_CENTER_RESIDENT_SETTING__${alarmStore.alarmType}`;
  });
  const filterMode = computed(() => {
    return alarmStore.filterMode;
  });
  const showAlarmModule = computed(() => {
    return filterMode.value === EMode.ui;
  });

  const favoriteList = computed(() => {
    return (
      alarmStore.favoriteList.map(item => ({
        groupName: '',
        id: item.id,
        name: item.name,
        config: {
          queryString: item?.params?.query_string || '',
          where: [],
          commonWhere: [],
        },
      })) || []
    );
  });

  watch(
    () => alarmStore.alarmType,
    async v => {
      const data = await alarmStore.alarmService.getListSearchFavorite({ search_type: v });
      alarmStore.favoriteList = data;
    },
    { immediate: true }
  );

  function handleConditionChange(val) {
    alarmStore.conditions = val;
  }
  function handleQueryStringChange(val: string) {
    alarmStore.queryString = val;
  }
  function handleFilterModeChange(val: EMode) {
    alarmStore.filterMode = val;
  }

  function handleResidentConditionChange(val) {
    alarmStore.residentCondition = val.map(item => ({
      ...item,
      condition: 'and',
    }));
  }
  function handleQuery() {
    alarmStore.refreshImmediate = random(4);
  }

  function getRetrievalFilterValueData(params: IGetValueFnParams) {
    return getFieldsOptionValuesProxy(params);
  }

  function getFieldsOptionValuesProxy(params: any) {
    function getMapKey(params: IParams) {
      return `${alarmStore.alarmType}____${params.fields.join('')}____`;
    }
    return new Promise(resolve => {
      if (params?.isInit__) {
        candidateValueMap = new Map();
      }
      const searchValue = String(params.where?.[0]?.value?.[0] || '');
      const searchValueLower = searchValue.toLocaleLowerCase();
      const candidateItem = candidateValueMap.get(getMapKey(params));
      if (candidateItem?.isEnd && !params?.query_string) {
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
        alarmStore.alarmService
          .getRetrievalFilterValues(
            {
              ...alarmStore.commonFilterParams,
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
            const values = res.fields?.find(f => f.field === params?.fields?.[0])?.buckets || [];
            const isEnd = values.length < params.limit;
            const newMap = new Map();
            if (!searchValue && isEnd) {
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
    condition,
    queryString,
    residentSettingOnlyId,
    filterMode,
    favoriteList,
    residentCondition,
    showAlarmModule,
    handleQuery,
    handleConditionChange,
    handleQueryStringChange,
    handleFilterModeChange,
    getRetrievalFilterValueData,
    handleResidentConditionChange,
  };
}
