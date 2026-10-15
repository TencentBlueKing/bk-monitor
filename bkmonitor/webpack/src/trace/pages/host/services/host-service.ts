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
import { getTopoTree } from 'monitor-api/modules/commons';
import { searchHostInfo, searchHostMetric } from 'monitor-api/modules/performance';

import type { IHostTopoTree } from '../types';
import type { IHostBaseInfo, IHostMetricInfo } from '../types/host';
import type { EHostQuickCategory } from '../types/host-list';
import type { HostScopeParams } from '../utils/share-scope';

/**
 * @description: 获取基础主机列表, 这个 API 要更快，但是不包含指标数据, 用于主机列表第一屏渲染
 * @returns {Promise<IHostBaseInfo[]>} 基础主机列表
 */
export const getHostInfoList = async (scope: HostScopeParams = {}) => {
  const data: IHostBaseInfo[] = await searchHostInfo(scope, { needMessage: false, reject403: true });
  return data;
};

export interface IHostInfoPage {
  items: IHostBaseInfo[];
  page: number;
  page_size: number;
  total: number;
}

export const getHostInfoPage = async (params: HostScopeParams & { page: number; page_size: number }) => {
  const data: IHostInfoPage = await searchHostInfo(params, { needMessage: false, reject403: true });
  return data;
};

const searchHostMetricStats = request('post', 'rest/v2/performance/search_host_metric_stats/');

export const getHostMetricStats = async (
  params: HostScopeParams & {
    category: Exclude<EHostQuickCategory, 'alarm'>;
    end_time: number;
    start_time: number;
  }
): Promise<{ complete: boolean; value: null | number }> => {
  return await searchHostMetricStats(params, { needMessage: false, reject403: true });
};

/**
 * @description: 获取带指标数据的主机列表 , 这个 API 要慢一些，但是包含所有的 host 指标数据，用于主机列表补充渲染
 * @returns {Promise<IHostMetricInfo[]>} 带指标数据的主机列表
 */
export const getHostMetricInfoList = async (
  params: HostScopeParams & {
    bk_host_ids?: number[];
    end_time: number;
    start_time: number;
  }
): Promise<Record<string, IHostMetricInfo>> => {
  return await searchHostMetric(params, { needMessage: false, reject403: true });
};

/**
 * @description: 获取主机拓扑树, 根据业务ID获取主机拓扑树
 * @param bizId 业务ID
 * @returns {Promise<IHostTopoTree[]>} 主机拓扑树
 */
export const getHostTopoTreeByBizId = async (
  bizId: number | string = window.cc_biz_id,
  scope: HostScopeParams = {},
  includeHosts = true
) => {
  const data: IHostTopoTree[] = await getTopoTree({
    bk_biz_id: bizId,
    ...scope,
    condition_list: [],
    ...(includeHosts ? { instance_type: 'host' } : {}),
    remove_empty_nodes: false,
  });
  return data;
};

export interface HostListQuery {
  basePromise: Promise<IHostBaseInfo[]>;
  expiresAt: number;
  key: string;
  metricPromise: Promise<Record<string, IHostMetricInfo>>;
  resolved: boolean;
  timeParams: TimeParams;
  timer?: number;
}

type CacheWindow = Window & { __MONITOR_HOST_LIST_QUERY__?: HostListQuery };
type TimeParams = { end_time: number; start_time: number };

const getCacheWindow = () => (window.rawWindow || window) as CacheWindow;

export const clearHostListQueryCache = (query: HostListQuery | null) => {
  if (!query) return;
  const owner = getCacheWindow();
  if (owner.__MONITOR_HOST_LIST_QUERY__ !== query) return;
  owner.clearTimeout(query.timer);
  delete owner.__MONITOR_HOST_LIST_QUERY__;
};

export const getHostListQuery = (
  key: null | string,
  scope: HostScopeParams,
  getTimeParams: () => TimeParams,
  forceRefresh: boolean
): HostListQuery | null => {
  if (!key || scope.bk_host_id != null || (scope.bk_obj_id && scope.bk_inst_id != null)) return null;
  const owner = getCacheWindow();
  const cached = owner.__MONITOR_HOST_LIST_QUERY__;
  const now = Date.now();
  if (!forceRefresh && cached?.key === key && cached.expiresAt > now) return cached;
  clearHostListQueryCache(cached);

  const timeParams = getTimeParams();
  const query: HostListQuery = {
    key,
    // 从查询发起计时，命中不续期，避免相对时间窗口不断变旧。
    expiresAt: now + 60_000,
    timeParams,
    basePromise: getHostInfoList(scope),
    metricPromise: getHostMetricInfoList({ ...scope, ...timeParams }),
    resolved: false,
  };
  // 宿主 window 保留一份查询，子应用及 Worker 仍按原生命周期销毁。
  owner.__MONITOR_HOST_LIST_QUERY__ = query;
  query.timer = owner.setTimeout(() => clearHostListQueryCache(query), query.expiresAt - now);
  void Promise.all([query.basePromise, query.metricPromise]).then(
    () => {
      query.resolved = true;
    },
    () => clearHostListQueryCache(query)
  );
  return query;
};
