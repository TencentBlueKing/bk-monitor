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
/** 旧版主机监控 query 里，新版页面已经能直接消费的键。 */
const PASS_QUERY_KEYS = [
  'search',
  'panelKey',
  'queryString',
  'keyword',
  'from',
  'to',
  'timezone',
  'refreshInterval',
  'dashboardId',
  'method',
  'interval',
  'compares',
  'timeOffset',
  'activeTab',
  'activeCategory',
  'hostProcessName',
  'hostProcessKeyword',
  'where',
  'filterExpanded',
  'nodeId',
  'metricAggregationState',
  'processMetricAggregationState',
  'shareLink',
  'lockSearch',
  'shareTargetType',
  'shareBkHostId',
  'shareBkObjId',
  'shareBkInstId',
];

/** ip-云区域。新版主机页打开后再换成 bk_host_id，跳转本身不等待查询。 */
export const LEGACY_IPV4_QUERY = 'legacyIpv4';

export type HostMonitorQuery = Record<string, HostMonitorQueryValue>;

export type HostMonitorQueryValue = Array<null | string> | null | number | string | undefined;

export type LegacyHostRoute = {
  params?: { id?: string; process?: string };
  path: string;
  query?: HostMonitorQuery;
};

const queryValue = (value: HostMonitorQueryValue) => {
  if (Array.isArray(value)) return value[0] == null ? '' : String(value[0]);
  if (value == null) return '';
  return String(value);
};

/** 新版节点 id 只接受正整数 bk_host_id。 */
export const isBkHostId = (id: string) => /^[1-9]\d*$/.test(id);

/** 旧详情把 IPv4 和云区域拼成 ip-cloudId。 */
export const splitLegacyIpv4HostId = (id: string) => {
  if (!id.includes('-')) return null;
  const [ip, cloudId] = id.split('-');
  if (!ip || cloudId == null || !/^\d+$/.test(cloudId)) return null;
  return { ip, cloudId };
};

const pickPassThroughQuery = (query: HostMonitorQuery = {}) => {
  const next: Record<string, string> = {};
  for (const key of PASS_QUERY_KEYS) {
    const value = queryValue(query[key]);
    if (value !== '') next[key] = value;
  }
  return next;
};

/** 生成新版主机监控的 path 与 query。进程名落到 activeTab + hostProcessName。 */
export const buildHostMonitorTarget = (options: {
  bkHostId?: string;
  processName?: string;
  query?: HostMonitorQuery;
}) => {
  const query = pickPassThroughQuery(options.query);
  const processName = options.processName || queryValue(options.query?.['var-display_name']);
  if (processName) {
    query.activeTab = 'process';
    query.hostProcessName = processName;
  }
  const bkHostId = options.bkHostId && isBkHostId(options.bkHostId) ? options.bkHostId : '';
  return {
    path: bkHostId ? `/trace/host/${bkHostId}` : '/trace/host',
    query,
  };
};

export const hostMonitorHash = (target: { path: string; query: Record<string, string> }) => {
  const search = new URLSearchParams(target.query).toString();
  return search ? `#${target.path}?${search}` : `#${target.path}`;
};

/**
 * 把旧版 /performance 路由规划成新版地址。
 * ip-云区域只写入 legacyIpv4，主机 id 由新版页面打开后查询。
 */
export const planLegacyHostRedirect = (to: LegacyHostRoute) => {
  const query = to.query || {};
  const isDetail = to.path.startsWith('/performance/detail');
  const processName = to.params?.process || '';
  if (!isDetail) return buildHostMonitorTarget({ query, processName });
  const rawId = to.params?.id || '';
  const filterHostId = queryValue(query['filter-bk_host_id']);
  const bkHostId = isBkHostId(rawId) ? rawId : isBkHostId(filterHostId) ? filterHostId : '';
  if (bkHostId) return buildHostMonitorTarget({ bkHostId, query, processName });
  const legacy = splitLegacyIpv4HostId(rawId);
  if (legacy) {
    const target = buildHostMonitorTarget({ query, processName });
    target.query[LEGACY_IPV4_QUERY] = `${legacy.ip}-${legacy.cloudId}`;
    return target;
  }
  const target = buildHostMonitorTarget({ query, processName });
  if (rawId && !target.query.keyword && !target.query.queryString) target.query.keyword = rawId;
  return target;
};

/** 同步生成新版 hash。ip-云区域保留在 legacyIpv4，不在这里查主机。 */
export const buildSyncLegacyHostHash = (input: { id?: string; processName?: string; query?: HostMonitorQuery }) => {
  const id = input.id ? String(input.id) : '';
  return hostMonitorHash(
    planLegacyHostRedirect({
      path: id ? '/performance/detail/placeholder' : '/performance',
      params: { id, process: input.processName || '' },
      query: input.query,
    })
  );
};

export const parseAppHash = (hash: string) => {
  const value = hash.startsWith('#') ? hash.slice(1) : hash;
  const queryIndex = value.indexOf('?');
  const path = queryIndex === -1 ? value : value.slice(0, queryIndex);
  const query: Record<string, string> = {};
  const search = queryIndex === -1 ? '' : value.slice(queryIndex + 1);
  new URLSearchParams(search).forEach((item, key) => {
    query[key] = item;
  });
  return { path, query };
};
