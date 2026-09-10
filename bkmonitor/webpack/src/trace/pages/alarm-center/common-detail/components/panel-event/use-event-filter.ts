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

import { eventTopK as apmEventTopK, eventViewConfig as apmEventViewConfig } from 'monitor-api/modules/apm_event';
import { eventTopK, eventViewConfig } from 'monitor-api/modules/data_explorer';

import { EFieldType } from '../../../../../components/retrieval-filter/typing';

import type { IFilterField, IGetValueFnParams } from '../../../../../components/retrieval-filter/typing';

/** 告警关联事件接口返回的查询配置，与事件检索接口入参同构 */
export interface IAlertEventQueryConfig {
  app_name?: string;
  bk_biz_id?: number;
  end_time?: number;
  query_configs?: Record<string, any> | Record<string, any>[];
  service_name?: string;
  start_time?: number;
}

interface ICandidateValueItem {
  count: number;
  isEnd: boolean;
  values: { id: string; name: string }[];
}

/**
 * @description 把事件检索的字段配置转换为筛选组件需要的格式
 * 事件接口返回 is_option_enabled / supported_operations，
 * 而 vue3 版筛选组件读的是 isEnableOptions / methods，且 methods.options 是数组。
 */
export function formatEventRetrievalFields(fields: Record<string, any>[]): IFilterField[] {
  return (fields || []).map(item => ({
    name: item.name,
    alias: item.alias || item.name,
    type: (item.type || EFieldType.keyword) as EFieldType,
    isEnableOptions: !!item.is_option_enabled,
    methods: (item.supported_operations || []).map((operation: Record<string, any>) => ({
      alias: operation.alias,
      value: operation.value,
      options: operation.options ? [operation.options] : undefined,
    })),
  }));
}

/**
 * @function useEventFilter 关联事件筛选条件 hook
 * @description 提供筛选字段列表与候选值的获取能力，数据源与「事件检索」页保持一致
 */
export function useEventFilter() {
  let axiosController = new AbortController();
  let candidateValueMap = new Map<string, ICandidateValueItem>();
  let commonQueryConfig: IAlertEventQueryConfig = {};

  function setQueryConfig(queryConfig: IAlertEventQueryConfig) {
    commonQueryConfig = queryConfig || {};
    candidateValueMap = new Map();
  }

  /** 拉取可筛选的字段列表 */
  async function getFieldList(): Promise<IFilterField[]> {
    const queryConfig = pickQueryConfig(commonQueryConfig);
    if (!queryConfig?.table) return [];
    const apiFunc = isApmQueryConfig(commonQueryConfig) ? apmEventViewConfig : eventViewConfig;
    const data = await apiFunc(
      {
        bk_biz_id: commonQueryConfig.bk_biz_id,
        data_sources: [
          {
            data_source_label: queryConfig.data_source_label,
            data_type_label: queryConfig.data_type_label,
            table: queryConfig.table,
          },
        ],
        app_name: commonQueryConfig.app_name,
        service_name: commonQueryConfig.service_name,
        start_time: commonQueryConfig.start_time,
        end_time: commonQueryConfig.end_time,
      },
      { needMessage: false }
    ).catch(() => ({ field: [] }));
    return formatEventRetrievalFields(data?.field || []);
  }

  function getMapKey(fields: string[]) {
    const queryConfig = pickQueryConfig(commonQueryConfig);
    return `${queryConfig?.table}____${commonQueryConfig.app_name}____${commonQueryConfig.service_name}____${fields.join('')}____`;
  }

  /** 拉取字段候选值，逻辑与事件检索一致：一次拉完就本地过滤，拉不完则每次都请求 */
  function getFieldsOptionValues(params: IGetValueFnParams) {
    return new Promise<{ count: number; list: { id: string; name: string }[] }>(resolve => {
      const queryConfig = pickQueryConfig(commonQueryConfig);
      const fields = params?.fields || [];
      if (!queryConfig?.table || !fields.length) {
        resolve({ count: 0, list: [] });
        return;
      }
      if (params?.isInit__) {
        candidateValueMap = new Map();
      }
      const searchValue = String(params.where?.[0]?.value?.[0] || '');
      const searchValueLower = searchValue.toLocaleLowerCase();
      const candidateItem = candidateValueMap.get(getMapKey(fields));
      if (candidateItem?.isEnd && !params?.queryString) {
        const list = searchValue
          ? candidateItem.values.filter(item =>
              `${item.id}${item.name}`.toLocaleLowerCase().includes(searchValueLower)
            )
          : candidateItem.values.slice(0, params.limit);
        resolve({ count: list.length, list });
        return;
      }
      axiosController.abort();
      axiosController = new AbortController();
      const apiFunc = isApmQueryConfig(commonQueryConfig) ? apmEventTopK : eventTopK;
      apiFunc(
        {
          bk_biz_id: commonQueryConfig.bk_biz_id,
          limit: params?.limit || 5,
          fields,
          query_configs: [
            {
              data_source_label: queryConfig.data_source_label,
              data_type_label: queryConfig.data_type_label,
              table: queryConfig.table,
              filter_dict: {},
              where: params?.where || [],
              group_by: [],
              query_string: params?.queryString || '',
            },
          ],
          app_name: commonQueryConfig.app_name,
          service_name: commonQueryConfig.service_name,
          start_time: commonQueryConfig.start_time,
          end_time: commonQueryConfig.end_time,
        },
        { signal: axiosController.signal, needMessage: false }
      )
        .then(res => {
          const values =
            res?.[0]?.list?.map((item: Record<string, any>) => ({
              id: item.value,
              name: item.alias ?? item.value,
            })) || [];
          const isEnd = values.length < (params?.limit || 5);
          const newMap = new Map<string, ICandidateValueItem>();
          if (!searchValue && isEnd) {
            newMap.set(getMapKey(fields), { values, isEnd, count: values.length });
          }
          candidateValueMap = newMap;
          resolve({ count: values.length, list: values });
        })
        .catch(err => {
          if (err?.message !== 'canceled') {
            resolve({ count: 0, list: [] });
          }
        });
    });
  }

  return {
    setQueryConfig,
    getFieldList,
    getFieldsOptionValues,
  };
}

/** APM 告警走 apm_event 接口，其余走 data_explorer 接口 */
function isApmQueryConfig(queryConfig: IAlertEventQueryConfig) {
  return !!queryConfig?.app_name;
}

/** 告警关联事件接口的 query_config 里，query_configs 有时是单个对象（非 APM 场景后端做了收敛） */
export function pickQueryConfig(queryConfig: IAlertEventQueryConfig): null | Record<string, any> {
  const configs = queryConfig?.query_configs;
  if (!configs) return null;
  return Array.isArray(configs) ? configs[0] || null : configs;
}
