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

import { HOST_METRIC_SNAPSHOT_SECTIONS } from '../types/host-metric-progressive';

import type { IHostTopoTree } from '../types';
import type { IHostBaseInfo, IHostMetricInfo } from '../types/host';
import type {
  HostMetricProgressiveState,
  HostMetricSnapshotSectionName,
  IHostMetricSnapshotPollQuery,
  IHostMetricSnapshotQuery,
  IHostMetricSnapshotResult,
  IHostMetricSnapshotService,
} from '../types/host-metric-progressive';
import type { HostScopeParams } from '../utils/share-scope';

interface IHostMetricSnapshotResponse {
  canonical_end_time?: number;
  canonical_start_time?: number;
  data?: Partial<Record<HostMetricSnapshotSectionName, Record<string, Partial<IHostMetricInfo>>>>;
  expired?: boolean;
  failed_sections?: HostMetricSnapshotSectionName[];
  host_count?: number;
  host_ids_hash?: string;
  retry_after?: number;
  revision?: number;
  snapshot_id?: string;
  state: HostMetricProgressiveState;
  sections?: Partial<
    Record<HostMetricSnapshotSectionName, { error?: string; revision: number; state: HostMetricProgressiveState }>
  >;
}

const createHostMetricSnapshot = request('post', 'rest/v2/performance/host_metric_snapshot/');
const retrieveHostMetricSnapshot = request('get', 'rest/v2/performance/host_metric_snapshot/{pk}/');

const toSnapshotRequestParams = (query: IHostMetricSnapshotQuery) => ({
  bk_biz_id: query.bkBizId,
  ...(query.bkHostId === undefined ? {} : { bk_host_id: query.bkHostId }),
  ...(query.bkInstId === undefined ? {} : { bk_inst_id: query.bkInstId }),
  ...(query.bkObjId === undefined ? {} : { bk_obj_id: query.bkObjId }),
  end_time: query.endTime,
  start_time: query.startTime,
});

const toSnapshotResult = (
  response: IHostMetricSnapshotResponse,
  fallbackQuery: IHostMetricSnapshotQuery,
  includeData = true
): IHostMetricSnapshotResult => ({
  canonicalEndTime:
    typeof response.canonical_end_time === 'number' && Number.isFinite(response.canonical_end_time)
      ? response.canonical_end_time
      : fallbackQuery.endTime,
  canonicalStartTime:
    typeof response.canonical_start_time === 'number' && Number.isFinite(response.canonical_start_time)
      ? response.canonical_start_time
      : fallbackQuery.startTime,
  expired: !!response.expired,
  failedSections: response.failed_sections || [],
  hostCount: response.host_count || 0,
  hostIdsHash: response.host_ids_hash || '',
  retryAfterMs: response.retry_after === undefined ? undefined : response.retry_after * 1000,
  revision: response.revision || 0,
  sections: includeData
    ? HOST_METRIC_SNAPSHOT_SECTIONS.flatMap(name =>
        response.data?.[name] ? [{ data: response.data[name], name }] : []
      )
    : [],
  snapshotId: response.snapshot_id,
  status: response.state,
});

const hashHostIds = async (hostIds: number[]) => {
  const canonical = [...new Set(hostIds)].sort((left, right) => left - right).join(',');
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(canonical));
  return [...new Uint8Array(digest)].map(value => value.toString(16).padStart(2, '0')).join('');
};

export const hostMetricSnapshotService: IHostMetricSnapshotService = {
  create: async query => {
    const params = toSnapshotRequestParams(query);
    const response = await createHostMetricSnapshot<typeof params, IHostMetricSnapshotResponse>(params, {
      isAsync: false,
      needMessage: false,
    });
    return toSnapshotResult(response, query, false);
  },
  hashHostIds,
  poll: async (query: IHostMetricSnapshotPollQuery) => {
    const params = {
      ...toSnapshotRequestParams(query),
      since_revision: query.sinceRevision,
    };
    const response = await retrieveHostMetricSnapshot<typeof params, IHostMetricSnapshotResponse>(
      query.snapshotId,
      params,
      { isAsync: false, needMessage: false }
    );
    return toSnapshotResult(response, query);
  },
};

/**
 * @description: 获取基础主机列表, 这个 API 要更快，但是不包含指标数据, 用于主机列表第一屏渲染
 * @returns {Promise<IHostBaseInfo[]>} 基础主机列表
 */
export const getHostInfoList = async (scope: HostScopeParams = {}) => {
  const data: IHostBaseInfo[] = await searchHostInfo(scope);
  return data;
};

/**
 * @description: 获取带指标数据的主机列表 , 这个 API 要慢一些，但是包含所有的 host 指标数据，用于主机列表补充渲染
 * @returns {Promise<IHostMetricInfo[]>} 带指标数据的主机列表
 */
export const getHostMetricInfoList = async (
  params: HostScopeParams & {
    bk_host_ids: number[];
    end_time: number;
    query_mode?: 'full' | 'page';
    start_time: number;
  }
) => {
  return await searchHostMetric(params);
};

/**
 * @description: 获取主机拓扑树, 根据业务ID获取主机拓扑树
 * @param bizId 业务ID
 * @returns {Promise<IHostTopoTree[]>} 主机拓扑树
 */
export const getHostTopoTreeByBizId = async (
  bizId: number | string = window.cc_biz_id,
  scope: HostScopeParams = {}
) => {
  const data: IHostTopoTree[] = await getTopoTree({
    bk_biz_id: bizId,
    ...scope,
    condition_list: [],
    instance_type: 'host',
    remove_empty_nodes: false,
  });
  return data;
};
