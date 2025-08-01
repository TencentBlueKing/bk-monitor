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
import {
  eventDownloadTopK as apmEventDownloadTopK,
  eventLogs as apmEventLogs,
  eventStatisticsGraph as apmEventStatisticsGraph,
  eventStatisticsInfo as apmEventStatisticsInfo,
  eventTopK as apmEventTopK,
  eventTotal as apmEventTotal,
  eventViewConfig as apmEventViewConfig,
} from 'monitor-api/modules/apm_event';
import {
  eventDownloadTopK,
  eventLogs,
  eventStatisticsGraph,
  eventStatisticsInfo,
  eventTopK,
  eventTotal,
  eventViewConfig,
} from 'monitor-api/modules/data_explorer';
import { bkMessage, makeMessage } from 'monitor-api/utils';

import type { ExploreTableRequestParams, ExploreTotalRequestParams, ITopKField, ITopKRequestParams } from './typing';
export enum APIType {
  APM = 'apm', // apm
  MONITOR = 'monitor', // monitor default
}

/**
 * @description: 获取事件图表配置数据接口枚举
 */
export enum EventTimeSeriesApiEnum {
  /** APM 获取事件图表配置接口 */
  APM = 'apm_event.eventTimeSeries',
  /** 事件检索获取事件图表配置数据接口 */
  MONITOR = 'data_explorer.eventTimeSeries', // monitor default
}

/**
 * @description: 获取事件top k
 * @param params
 * @param type
 * @returns
 */
export const getEventTopK = (
  params: ITopKRequestParams,
  type = APIType.MONITOR,
  config = {}
): Promise<ITopKField[]> => {
  const apiFunc = type === APIType.APM ? apmEventTopK : eventTopK;
  return apiFunc(params, { needMessage: false, ...config }).catch(() => []);
};

/** 获取topk统计信息 */
export const getTopKStatisticInfo = (params: any, type = APIType.MONITOR, config = {}) => {
  const apiFunc = type === APIType.APM ? apmEventStatisticsInfo : eventStatisticsInfo;
  return apiFunc(params, { needMessage: false, ...config });
};

/** 获取topk图表数据 */
export const getTopKStatisticGraph = (params: any, type = APIType.MONITOR, config = {}) => {
  const apiFunc = type === APIType.APM ? apmEventStatisticsGraph : eventStatisticsGraph;
  return apiFunc(params, { needMessage: false, ...config });
};

export const getEventViewConfig = (params: any, type = APIType.MONITOR) => {
  const apiFunc = type === APIType.APM ? apmEventViewConfig : eventViewConfig;
  return apiFunc(params, { isDataParams: true }).catch(() => ({ display_fields: [], entities: [], field: [] }));
};

export const getDownloadTopK = (params, type = APIType.MONITOR) => {
  const apiFunc = type === APIType.APM ? apmEventDownloadTopK : eventDownloadTopK;
  return apiFunc(params, { isDataParams: true }).catch(err => err);
};

/**
 * @description: 获取事件总数
 * @param {ExploreTotalRequestParams} params
 * @param {APIType} type
 */
export const getEventTotal = (params: ExploreTotalRequestParams, type = APIType.MONITOR, requestConfig = {}) => {
  const apiFunc = type === APIType.APM ? apmEventTotal : eventTotal;
  const config = { needMessage: false, ...requestConfig };
  return apiFunc(params, config).catch(err => {
    const isAborted = requestErrorMessage(err);
    return {
      total: 0,
      isAborted,
    };
  });
};

/**
 * @description: 获取table表格日志数据
 * @param {ExploreTableRequestParams} params
 * @param {APIType} type
 */
export const getEventLogs = (params: ExploreTableRequestParams, type = APIType.MONITOR, requestConfig = {}) => {
  const apiFunc = type === APIType.APM ? apmEventLogs : eventLogs;
  const config = { needMessage: false, ...requestConfig };
  return apiFunc(params, config).catch(err => {
    const isAborted = requestErrorMessage(err);
    return { list: [], isAborted };
  });
};

/**
 * @description: 获取图表配置数据使用的接口
 * @param {APIType} type
 * @returns {EventTimeSeries} 请求接口地址
 */
export const getEventTimeSeries = (type = APIType.MONITOR) => {
  const api = type === APIType.APM ? EventTimeSeriesApiEnum.APM : EventTimeSeriesApiEnum.MONITOR;
  return api;
};

type ICandidateValueMap = Map<
  string,
  {
    count: number;
    isEnd: boolean;
    values: { id: string; name: string }[];
  }
>;

type TRetrievalFilterCandidateValueParams = any & {
  isInit__?: boolean;
};
export class RetrievalFilterCandidateValue {
  axiosController = new AbortController();
  candidateValueMap: ICandidateValueMap = new Map();

  getFieldsOptionValuesProxy(params: TRetrievalFilterCandidateValueParams, apiType: APIType) {
    return new Promise((resolve, _reject) => {
      try {
        if (params?.isInit__) {
          this.candidateValueMap = new Map();
        }
        const queryConfig = params.query_configs[0];
        const { where } = queryConfig;
        const searchValue = String(where?.[0]?.value?.[0] || '');
        const candidateItem = this.candidateValueMap.get(this.getMapKey(params));
        const searchValueLower = searchValue.toLocaleLowerCase();
        if (!queryConfig?.query_string && candidateItem?.isEnd) {
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
          this.axiosController.abort();
          this.axiosController = new AbortController();
          getEventTopK(
            {
              ...params,
              isInit__: undefined,
            },
            apiType,
            {
              signal: this.axiosController.signal,
              needMessage: false,
            }
          )
            .then(res => {
              const data: any = res?.[0] || {};
              const values =
                data?.list?.map(item => ({
                  id: item.value,
                  name: item.alias,
                })) || [];
              const isEnd = values.length < params.limit;
              const newMap = new Map();
              if (!searchValue && isEnd) {
                newMap.set(this.getMapKey(params), {
                  values: values,
                  isEnd: isEnd,
                  count: data.length,
                });
              }
              this.candidateValueMap = newMap;
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
      } catch (err) {
        console.log(err);
        resolve({
          count: 0,
          list: [],
        });
      }
    });
  }
  getMapKey(params: TRetrievalFilterCandidateValueParams) {
    const queryConfig = params.query_configs[0];
    return `${queryConfig.data_source_label}____${queryConfig.data_type_label}____${
      queryConfig.table
    }____${params?.app_name}____${params?.service_name}____${params.fields.join('')}____`;
  }
}
/**
 * @description 请求错误时消息提示处理逻辑（ cancel 类型报错不进行提示）
 * @param err
 *
 */
function requestErrorMessage(err) {
  const message = makeMessage(err.error_details || err.message);
  let isAborted = false;
  if (message && err?.message !== 'canceled' && err?.message !== 'aborted') {
    bkMessage(message);
  } else {
    isAborted = true;
  }
  return isAborted;
}
