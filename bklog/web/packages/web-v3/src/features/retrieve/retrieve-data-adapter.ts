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

import type { FavoriteGroup } from './favorite-controller';
import type { LogField } from './field-controller';
import type { IndexSetItem } from './index-set-controller';
import type { LogRecord, SearchFetcher } from './retrieve-search-controller';
import type { QueryCondition, QueryMode, WorkbenchSnapshot } from './retrieve-workbench-controller';
import type { RetrieveTab } from './workspace-controller';

export interface RetrieveRouteState {
  indexSetId: string;
  spaceUid: string;
  bizId: string;
  tab: RetrieveTab;
}

export interface RetrieveBootstrapData {
  route: RetrieveRouteState;
  indexSets: IndexSetItem[];
  fields: LogField[];
  favorites: FavoriteGroup[];
  records: LogRecord[];
  errors: {
    indexSets?: string;
    fields?: string;
    favorites?: string;
  };
}

export interface TrendBucket {
  startTime: number;
  count: number;
}

export interface RetrieveSearchPayload {
  keyword: string;
  addition: QueryCondition[];
  search_mode: QueryMode;
  begin: number;
  size: number;
  start_time: number;
  end_time: number;
  index_set_id: string;
  space_uid: string;
  biz_id: string;
}

export interface DialogPayload {
  route: RetrieveRouteState;
  keyword: string;
  timeRange: { startTime: number; endTime: number };
  fields: string[];
  fallbackVisible: boolean;
}

const now = Date.now();
const FALLBACK_ROUTE: RetrieveRouteState = {
  indexSetId: '38077',
  spaceUid: 'bkcc__5000140',
  bizId: '5000140',
  tab: 'origin',
};

const FALLBACK_RECORDS: LogRecord[] = [
  {
    id: 'v2-1',
    dtEventTimeStamp: now - 60_000,
    log: 'runnerroll-auto-golds-29884785-zjhd2 当前为子进程: {"message":"remain 200","result":true}',
    indexSetId: '38077',
    serverIp: '30.184.131.27',
    path: '/data/bcs/service/docker/containers/runnerroll-auto-golds-json.log',
    status: 200,
  },
  {
    id: 'v2-2',
    dtEventTimeStamp: now - 180_000,
    log: 'runnerroll-auto-golds-29884780-h8ny4 当前暂无数据，本次不清理，不投放',
    indexSetId: '38077',
    serverIp: '30.184.131.28',
    path: '/data/bcs/service/docker/containers/runnerroll-auto-golds-json.log',
    status: 200,
  },
  {
    id: 'v2-3',
    dtEventTimeStamp: now - 300_000,
    log: 'runnerroll-auto-golds-29884775-bxdb2 当前为子进程: {"total":200,"percent":1}',
    indexSetId: '38077',
    serverIp: '30.184.131.29',
    path: '/data/bcs/service/docker/containers/runnerroll-auto-golds-json.log',
    status: 200,
  },
];

const FALLBACK_INDEX_SETS: IndexSetItem[] = [
  { id: '38077', name: '[采集项]2026_colecai_auto_golds_stdout_std', scenario: 'log', tableId: 'space_4248884_bklog.bcs_k8s_26888_2026_colecai_auto_golds_stdout_52thw_std' },
  { id: '16176', name: '[采集项]container log demo', scenario: 'log', tableId: '5000140_bklog_container_log_demo' },
];

const FALLBACK_FIELDS: LogField[] = [
  { name: 'dtEventTimeStamp', type: 'number', kind: 'date', alias: '时间', visible: true, analyzable: false },
  { name: '__ext.io_kubernetes_pod', type: 'string', kind: 'keyword', alias: 'pod', visible: true, analyzable: true },
  { name: 'log', type: 'string', kind: 'text', alias: '日志', visible: true, analyzable: true },
  { name: 'serverIp', type: 'string', kind: 'keyword', alias: 'IP', visible: false, analyzable: true },
  { name: 'path', type: 'string', kind: 'text', alias: '路径', visible: false, analyzable: false },
  { name: 'status', type: 'number', kind: 'integer', alias: '状态码', visible: false, analyzable: true },
];

const FALLBACK_FAVORITES: FavoriteGroup[] = [
  {
    groupId: 'private',
    groupName: '个人收藏',
    visibleType: 'private',
    favorites: [
      { id: 'fav-v2-error', name: '错误日志', keyword: 'error', groupId: 'private', groupName: '个人收藏', visibleType: 'private', indexSetId: '38077' },
    ],
  },
  {
    groupId: 'public',
    groupName: '公共收藏',
    visibleType: 'public',
    favorites: [
      { id: 'fav-v2-remain', name: 'remain 200', keyword: 'remain 200', groupId: 'public', groupName: '公共收藏', visibleType: 'public', indexSetId: '38077' },
    ],
  },
];

const normalizeTab = (value: string | null): RetrieveTab => (
  value === 'clustering' || value === 'grep' || value === 'graph' ? value : 'origin'
);

export function parseRetrieveRoute(url = window.location.href): RetrieveRouteState {
  const parsed = new URL(url);
  const hash = parsed.hash.replace(/^#/, '');
  const [path, query = ''] = hash.split('?');
  const params = new URLSearchParams(query);
  const indexSetId = path.split('/').filter(Boolean)[1] || FALLBACK_ROUTE.indexSetId;
  return {
    indexSetId,
    spaceUid: params.get('spaceUid') || FALLBACK_ROUTE.spaceUid,
    bizId: params.get('bizId') || FALLBACK_ROUTE.bizId,
    tab: normalizeTab(params.get('tab')),
  };
}

const readJson = async <T>(input: RequestInfo | URL, init?: RequestInit): Promise<T | null> => {
  const response = await fetch(input, init);
  if (!response.ok) {
    return null;
  }
  const data = await response.json();
  return data?.result === false ? null : data?.data ?? data;
};

const withFallback = <T>(items: T[], fallback: T[]): T[] => (items.length ? items : fallback);

const toFieldKind = (fieldType: string): LogField['kind'] => {
  if (fieldType === 'date') return 'date';
  if (fieldType === 'integer' || fieldType === 'long' || fieldType === 'number') return 'integer';
  if (fieldType === 'keyword') return 'keyword';
  return 'text';
};

const flattenLog = (value: unknown): string => {
  if (typeof value === 'string') return value;
  if (value == null) return '';
  return JSON.stringify(value);
};

const toRecord = (item: Record<string, unknown>, index: number, indexSetId: string): LogRecord => ({
  id: String(item.__id__ ?? item.id ?? index + 1),
  dtEventTimeStamp: Number(item.dtEventTimeStamp ?? item.time ?? item._time ?? Date.now()),
  log: flattenLog(item.log ?? item.message ?? item.origin_data ?? item),
  indexSetId,
  serverIp: String(item.serverIp ?? ''),
  path: String(item.path ?? ''),
  status: Number(item.status ?? (item.level === 'ERROR' ? 500 : 200)),
});

export const buildSearchPayload = (
  snapshot: WorkbenchSnapshot,
  options: { begin?: number; size?: number } = {},
): RetrieveSearchPayload => ({
  keyword: snapshot.queryState.keyword,
  addition: snapshot.queryState.conditions.map(item => ({ ...item })),
  search_mode: snapshot.queryState.mode,
  begin: options.begin ?? Math.max(0, (snapshot.queryState.page - 1) * (options.size ?? 50)),
  size: options.size ?? 50,
  start_time: snapshot.queryState.timeRange.startTime,
  end_time: snapshot.queryState.timeRange.endTime,
  index_set_id: snapshot.routeState.indexSetId,
  space_uid: snapshot.routeState.spaceUid,
  biz_id: snapshot.routeState.bizId,
});

export const buildDialogPayload = (
  snapshot: WorkbenchSnapshot,
  fields: LogField[],
  fallbackVisible = false,
): DialogPayload => ({
  route: { ...snapshot.routeState },
  keyword: snapshot.queryState.keyword,
  timeRange: { ...snapshot.queryState.timeRange },
  fields: fields.filter(item => item.visible).map(item => item.name),
  fallbackVisible,
});

const parseNdjsonRows = (payload: string, indexSetId: string): { records: LogRecord[]; total?: number } => {
  let total: number | undefined;
  const records: LogRecord[] = [];
  for (const line of payload.split(/\n+/).map(item => item.trim()).filter(Boolean)) {
    try {
      const item = JSON.parse(line);
      if (typeof item.total === 'number') total = item.total;
      if (item.event === 'row' && item.data) {
        records.push(toRecord(item.data, records.length, indexSetId));
      }
    } catch {
      // Ignore partial stream chunks from dev/mock payloads.
    }
  }
  return { records, total };
};

export const createDevSearchFetcher = (route: RetrieveRouteState, fallback = FALLBACK_RECORDS): SearchFetcher => (
  async ({ keyword, indexSetId, signal }) => {
    const activeId = indexSetId || route.indexSetId;
    try {
      const response = await fetch(`/api/v1/search/index_set/${activeId}/search/?stream=true`, {
        method: 'POST',
        signal,
        headers: {
          'content-type': 'application/json',
          'x-bk-space-uid': route.spaceUid,
          'x-bklog-timezone': 'Asia/Shanghai',
        },
        body: JSON.stringify({
          keyword,
          addition: [],
          search_mode: 'ui',
          begin: 0,
          size: 50,
          start_time: Date.now() - 15 * 60 * 1000,
          end_time: Date.now(),
          index_set_id: activeId,
          space_uid: route.spaceUid,
          biz_id: route.bizId,
        }),
      });
      if (response.ok) {
        const parsed = parseNdjsonRows(await response.text(), activeId);
        if (parsed.records.length) {
          return { list: parsed.records, total: parsed.total ?? parsed.records.length };
        }
      }
    } catch {
      // Fallback keeps the page useful when appdev is unavailable from V3 dev.
    }
    const normalized = keyword.trim().toLowerCase();
    const list = fallback.filter(item => !normalized || item.log.toLowerCase().includes(normalized));
    return { list, total: list.length };
  }
);

export async function loadRetrieveBootstrap(route = parseRetrieveRoute()): Promise<RetrieveBootstrapData> {
  try {
    const [indexSets, fields, favorites] = await Promise.all([
      readJson<Array<Record<string, unknown>>>(`/api/v1/search/index_set/?space_uid=${route.spaceUid}&is_group=true`),
      readJson<{ fields: Array<Record<string, unknown>> }>(`/api/v1/search/index_set/${route.indexSetId}/fields/?is_realtime=True`),
      readJson<Array<Record<string, unknown>>>(`/api/v1/search/favorite/list_by_group/?space_uid=${route.spaceUid}&order_type=NAME_ASC&source_type=index_set`),
    ]);
    const indexSetItems = (indexSets || []).slice(0, 30).map(item => ({
      id: String(item.index_set_id),
      name: String(item.index_set_name ?? item.index_set_id),
      scenario: String(item.scenario_id ?? 'log'),
      tableId: Array.isArray(item.indices) ? String((item.indices[0] as Record<string, unknown>)?.result_table_id ?? '') : '',
    })).filter(item => item.id);
    const fieldItems = (fields?.fields || []).slice(0, 40).map(item => ({
      name: String(item.field_name),
      type: item.field_type === 'long' || item.field_type === 'integer' ? 'number' as const : 'string' as const,
      kind: toFieldKind(String(item.field_type)),
      alias: String(item.field_alias || item.description || ''),
      visible: Boolean(item.is_display) || ['dtEventTimeStamp', 'log', '__ext.io_kubernetes_pod'].includes(String(item.field_name)),
      analyzable: String(item.field_type) !== 'date',
    })).filter(item => item.name);
    const favoriteGroups = (favorites || []).map(group => ({
      groupId: String(group.group_id),
      groupName: String(group.group_name ?? '收藏'),
      visibleType: group.group_type === 'private' ? 'private' as const : 'public' as const,
      favorites: ((group.favorites as Array<Record<string, unknown>> | undefined) || []).map(item => ({
        id: String(item.id),
        name: String(item.name ?? item.id),
        keyword: String((item.params as Record<string, unknown> | undefined)?.keyword ?? '*'),
        groupId: String(group.group_id),
        groupName: String(group.group_name ?? '收藏'),
        visibleType: group.group_type === 'private' ? 'private' as const : 'public' as const,
        indexSetId: String(item.index_set_id ?? route.indexSetId),
      })),
    }));
    return {
      route,
      indexSets: withFallback(indexSetItems, FALLBACK_INDEX_SETS),
      fields: withFallback(fieldItems, FALLBACK_FIELDS),
      favorites: withFallback(favoriteGroups, FALLBACK_FAVORITES),
      records: FALLBACK_RECORDS.map(item => ({ ...item, indexSetId: route.indexSetId })),
      errors: {
        indexSets: indexSetItems.length ? undefined : '索引集列表加载失败，已使用本地兜底数据',
        fields: fieldItems.length ? undefined : '索引字段列表查询失败，可点击刷新重试',
        favorites: favoriteGroups.length ? undefined : '收藏列表加载失败，已使用本地兜底数据',
      },
    };
  } catch {
    return {
      route,
      indexSets: FALLBACK_INDEX_SETS,
      fields: FALLBACK_FIELDS,
      favorites: FALLBACK_FAVORITES,
      records: FALLBACK_RECORDS.map(item => ({ ...item, indexSetId: route.indexSetId })),
      errors: {
        indexSets: '索引集列表加载失败，已使用本地兜底数据',
        fields: '索引字段列表查询失败，可点击刷新重试',
        favorites: '收藏列表加载失败，已使用本地兜底数据',
      },
    };
  }
}

export async function fetchRetrieveHistogram(route: RetrieveRouteState, timeRange: { startTime: number; endTime: number }): Promise<TrendBucket[]> {
  const data = await readJson<Array<Record<string, unknown>> | { buckets?: Array<Record<string, unknown>> }>(
    `/api/v1/search/index_set/${route.indexSetId}/aggs/date_histogram/`,
    {
      method: 'POST',
      headers: {
        'content-type': 'application/json',
        'x-bk-space-uid': route.spaceUid,
        'x-bklog-timezone': 'Asia/Shanghai',
      },
      body: JSON.stringify({
        start_time: timeRange.startTime,
        end_time: timeRange.endTime,
      }),
    },
  );
  const buckets = Array.isArray(data) ? data : data?.buckets;
  return (buckets || []).map(item => ({
    startTime: Number(item.start_time ?? item.startTime ?? item.key ?? item.time ?? Date.now()),
    count: Number(item.count ?? item.doc_count ?? item.value ?? 0),
  })).filter(item => item.count >= 0);
}
