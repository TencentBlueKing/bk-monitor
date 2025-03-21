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
  eventTopK as apmEventTopK,
  eventTotal as apmEventTotal,
  eventViewConfig as apmEventViewConfig,
  eventLogs as apmEventLogs,
} from 'monitor-api/modules/apm_event';
import {
  eventDownloadTopK,
  eventTopK,
  eventTotal,
  eventViewConfig,
  eventLogs,
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
export const getEventTotal = (params: ExploreTotalRequestParams, type = APIType.MONITOR) => {
  const apiFunc = type === APIType.APM ? apmEventTotal : eventTotal;
  return apiFunc(params).catch(() => ({
    total: 0,
  }));
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
    const message = makeMessage(err.error_details || err.message);
    if (message && err?.message !== 'canceled') {
      if (message) {
        bkMessage(message);
      }
    }
    return { list: [] };
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
