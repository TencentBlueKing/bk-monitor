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

import { queryBkDataToken } from 'monitor-api/modules/apm_meta';
import {
  listApplicationServices,
  query,
  queryLabels,
  queryLabelValues,
  queryProfileBarGraph,
  queryServicesDetail,
} from 'monitor-api/modules/apm_profile';
import { retrieveFavorite, updateFavorite } from 'monitor-api/modules/model';

import type {
  Application,
  ProfileQuery,
  ProfileResult,
  ProfilingFavorite,
  ProfilingFavoriteConfig,
  ServiceDetail,
  TrendResult,
} from '../types';

const requestOptions = (signal: AbortSignal) => ({ signal, needMessage: false });

export async function getApplications(bizId: number, signal: AbortSignal): Promise<Application[]> {
  const result = await listApplicationServices({ bk_biz_id: bizId }, requestOptions(signal));
  // 保留后端分组语义和顺序，不能仅凭 services 是否为空判断无数据应用。
  return [
    ...(result.normal || []).map(item => ({ ...item, has_data: true })),
    ...(result.no_data || []).map(item => ({ ...item, has_data: false })),
  ];
}

export function getApplicationToken(applicationId: number, signal: AbortSignal): Promise<string> {
  return queryBkDataToken(applicationId, {}, requestOptions(signal));
}

export function getExportUrl(params: ProfileQuery): string {
  const { start = params.start, end = params.end, ...filterLabels } = params.filter_labels;
  const search = new URLSearchParams();
  // 导出端点读取外层时间范围，不消费图表框选的嵌套 start/end。
  const query = {
    ...params,
    start,
    end,
    filter_labels: filterLabels,
    diff_filter_labels: {},
    is_compared: false,
    export_format: 'pprof',
  };
  for (const [key, value] of Object.entries(query)) {
    if (key === 'diagram_types') continue;
    search.set(key, typeof value === 'object' ? JSON.stringify(value) : String(value));
  }
  const base = process.env.NODE_ENV === 'development' ? '/' : window.site_url;
  return `${base}apm/profile_api/query/export/?${search}`;
}

export function getFavorite(id: number, signal: AbortSignal): Promise<ProfilingFavorite> {
  return retrieveFavorite(id, { type: 'profiling' }, requestOptions(signal));
}

export async function getLabelKeys(params: ProfileQuery, signal: AbortSignal): Promise<string[]> {
  const result = await queryLabels(params, requestOptions(signal));
  return result.label_keys || [];
}

export async function getLabelValues(
  params: ProfileQuery,
  field: string,
  limit: number,
  signal: AbortSignal
): Promise<string[]> {
  const result = await queryLabelValues(
    { ...params, label_key: field, rows: limit, offset: 0 },
    requestOptions(signal)
  );
  return (result.label_values || []).map(String);
}

export async function getProfile(params: ProfileQuery, signal: AbortSignal): Promise<ProfileResult> {
  const result = await query(params, requestOptions(signal));
  // samples 无数据时返回 HTTP 200 + 文案，而不是图表对象。
  if (typeof result === 'string' || !result) return {};
  return result;
}

export function getServiceDetail(
  params: {
    app_name: string;
    bk_biz_id: number;
    end_time: number;
    service_name: string;
    start_time: number;
  },
  signal: AbortSignal
): Promise<ServiceDetail> {
  return queryServicesDetail(params, requestOptions(signal));
}

export async function getTrend(params: ProfileQuery, signal: AbortSignal, trace = false): Promise<TrendResult> {
  const result = trace
    ? await queryProfileBarGraph(
        {
          bk_biz_id: params.bk_biz_id,
          app_name: params.app_name,
          service_name: params.service_name,
          data_type: params.data_type,
          // Trace 接口要求整数秒；相对时间含毫秒，不能仅除以单位倍率保留小数。
          start_time: Math.floor(params.start / 1000000),
          end_time: Math.floor(params.end / 1000000),
          filter_labels: params.filter_labels,
        },
        requestOptions(signal)
      )
    : await query(params, requestOptions(signal));
  return { series: result?.series || [] };
}

export function saveFavorite(id: number, config: ProfilingFavoriteConfig) {
  return updateFavorite(id, { type: 'profiling', config });
}
