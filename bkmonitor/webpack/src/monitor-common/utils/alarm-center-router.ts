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

/**
 * 新版告警中心（Alarm Center）跳转工具函数。
 *
 * 整站旧版"事件中心"（`#/event-center`、`#/event-action`、`#/event-center/detail/:id`、
 * `#/event-center/action-detail/:id`）统一切换到新版"告警中心"
 * （`#/trace/alarm-center`、`#/trace/alarm-center/detail/:alarmId`）。
 *
 * 工具函数集中处理新旧版本之间的 URL 参数兼容映射，避免在调用处散落硬编码的 hash。
 */

/** 列表页 hash path（不含 query） */
export const ALARM_CENTER_LIST_HASH = '#/trace/alarm-center';
/** 详情页 hash path 前缀（不含 alarmId） */
export const ALARM_CENTER_DETAIL_HASH_PREFIX = '#/trace/alarm-center/detail/';
/** 列表页命名路由 */
export const ALARM_CENTER_ROUTE_NAME = 'alarm-center';
/** 详情页命名路由 */
export const ALARM_CENTER_DETAIL_ROUTE_NAME = 'alarm-center-detail';

/** 旧版事件中心跳转入参（向后兼容字段） */
export interface ILegacyAlarmCenterQuery {
  /** 其他自定义字段（透传） */
  [key: string]: any;
  /** 旧版：处理记录 ID（会被转成 queryString=action_id : ${actionId}） */
  actionId?: number | string;
  /**
   * 旧版：左侧快捷筛选选中项 ID（如 `NOT_SHIELDED_ABNORMAL`、`MY_APPOINTEE`、`success` 等）
   * 新版告警中心改用 `quickFilterValue: [{ key, value }]` 表达，
   * 工具会按 alarmType + activeFilterId 自动映射到对应分类（MINE / STATUS / INCIDENT_LEVEL / action）。
   * 与 alarmType 同名时（即旧版 overview 总览项）不下发任何快捷筛选。
   */
  activeFilterId?: string;
  /** 透传到新版告警中心：列表当前选中告警业务 ID */
  alarmBizId?: number | string;
  /** 透传到新版告警中心：列表当前选中告警 ID（用于侧栏详情） */
  alarmId?: number | string;
  /** 新版：alarmType */
  alarmType?: 'action' | 'alert' | 'incident';
  /** 旧版：告警 ID（会被转成 queryString=id : ${alertId}） */
  alertId?: number | string;
  /** 透传到新版告警中心：进入后自动打开确认/屏蔽等弹窗 */
  autoShowAlertAction?: string;
  /** 通用：业务 ID 列表 */
  bizIds?: number[] | string | string[];
  /** 旧版：收敛记录 ID（会被转成 queryString=action_id : ${collectId}） */
  collectId?: number | string;
  /**
   * 旧版："condition" 字典，用于初始化新版快捷筛选
   * 例：{ STATUS: ['NOT_SHIELDED_ABNORMAL'] }
   * 不在本工具中转换，直接透传给新版告警中心兜底逻辑。
   */
  condition?: Record<string, number[] | string[]> | string;
  /** 通用：UI 模式条件 */
  conditions?: string;
  /** 透传到新版告警中心：当前页 */
  currentPage?: number | string;
  /** 透传到新版告警中心：默认收藏 ID */
  favorite_id?: number | string;
  /** 通用：检索模式 ui | queryString */
  filterMode?: 'queryString' | 'ui';
  /** 通用：开始时间 */
  from?: number | string;
  /** 透传到新版告警中心：最后一次快捷筛选分类数据 */
  lastQuickFilterCategoryData?: string;
  /** 旧版：指标 ID（会被转成 queryString=metric : ${metricId}） */
  metricId?: number | string;
  /** 通用：检索 DSL 字符串 */
  queryString?: string;
  /** 通用：快捷筛选值 */
  quickFilterValue?: string;
  /** 通用：自动刷新间隔 */
  refreshInterval?: number | string;
  /** 通用：常驻条件 */
  residentCondition?: string;
  /** 旧版：searchType（新版兼容字段） */
  searchType?: 'action' | 'alert' | 'incident';
  /** 透传到新版告警中心：是否展示侧栏详情 */
  showDetail?: boolean | string;
  /** 透传到新版告警中心：是否展示常驻设置按钮 */
  showResidentBtn?: boolean | string;
  /** 通用：表格排序 */
  sortOrder?: string;
  /** 旧版：specEvent 用于自动展开告警详情侧栏；新版改成 alarmId+showDetail */
  specEvent?: boolean | number | string;
  /** 通用：时区 */
  timezone?: string;
  /** 通用：结束时间 */
  to?: number | string;
}

/** 旧版字段集合，转换后会从 query 中移除 */
const LEGACY_FIELDS = new Set([
  'alertId',
  'actionId',
  'collectId',
  'metricId',
  'specEvent',
  'searchType',
  'activeFilterId',
]);

/**
 * `activeFilterId` → 新版 `quickFilterValue` 的分类映射。
 * 同一个 ID 在不同 alarmType 下可能没有对应分类（如 alert 下不存在 `success`），
 * 取值依赖当前 alarmType（默认 alert）。
 */
const ACTIVE_FILTER_ID_KEY_MAP: Record<'action' | 'alert' | 'incident', Record<string, string>> = {
  alert: {
    MINE: 'MINE',
    MY_APPOINTEE: 'MINE',
    MY_ASSIGNEE: 'MINE',
    MY_FOLLOW: 'MINE',
    MY_HANDLER: 'MINE',
    NOT_SHIELDED_ABNORMAL: 'STATUS',
    SHIELDED_ABNORMAL: 'STATUS',
    ABNORMAL: 'STATUS',
    RECOVERED: 'STATUS',
    CLOSED: 'STATUS',
  },
  action: {
    success: 'action',
    failure: 'action',
    running: 'action',
    shield: 'action',
    skipped: 'action',
  },
  incident: {
    MINE: 'MINE',
    MY_ASSIGNEE_INCIDENT: 'MINE',
    MY_HANDLER_INCIDENT: 'MINE',
    WARN: 'INCIDENT_LEVEL',
    ERROR: 'INCIDENT_LEVEL',
    INFO: 'INCIDENT_LEVEL',
  },
};

/** 新版告警中心 URL 不再持久化的字段；保留打印 warn 提示，但仍透传 */
const UNSUPPORTED_FIELDS = new Set(['promql', 'activePanel', 'chartInterval', 'batchAction']);

/**
 * 生成新版告警中心详情页 hash（含 `?query`）。
 * 兼容旧版 `event-center/detail/:id` 与 `event-center/action-detail/:id`，统一进入新版同一详情路径。
 */
export function getAlarmCenterDetailHash(alarmId: number | string, query?: ILegacyAlarmCenterQuery): string {
  const transformed = transformLegacyAlarmQuery(query);
  const search = stringifyQuery(transformed);
  const base = `${ALARM_CENTER_DETAIL_HASH_PREFIX}${encodeURIComponent(String(alarmId))}`;
  return search ? `${base}?${search}` : base;
}

/**
 * 用于 Vue Router 的 `router.push` / `router.resolve` 入参（详情命名路由）。
 * 旧版 `event-center-detail` / `event-center-action-detail` 都映射到新版 `alarm-center-detail`。
 */
export function getAlarmCenterDetailRouteLocation(
  alarmId: number | string,
  query?: ILegacyAlarmCenterQuery
): {
  name: string;
  params: Record<string, any>;
  query: Record<string, any>;
} {
  return {
    name: ALARM_CENTER_DETAIL_ROUTE_NAME,
    params: { alarmId: String(alarmId) },
    query: transformLegacyAlarmQuery(query),
  };
}

/** 详情页完整跳转 URL */
export function getAlarmCenterDetailUrl(
  alarmId: number | string,
  query?: ILegacyAlarmCenterQuery,
  bizId?: number | string
): string {
  return getAlarmCenterUrl({ hash: getAlarmCenterDetailHash(alarmId, query), bizId });
}

/**
 * 生成新版告警中心列表页 hash（含 `?query`）。
 * @example getAlarmCenterListHash({ queryString: 'id : 123' })
 *   → '#/trace/alarm-center?queryString=id%20%3A%20123&filterMode=queryString'
 */
export function getAlarmCenterListHash(query?: ILegacyAlarmCenterQuery): string {
  const transformed = transformLegacyAlarmQuery(query);
  const search = stringifyQuery(transformed);
  return search ? `${ALARM_CENTER_LIST_HASH}?${search}` : ALARM_CENTER_LIST_HASH;
}

/** 列表页完整跳转 URL */
export function getAlarmCenterListUrl(query?: ILegacyAlarmCenterQuery, bizId?: number | string): string {
  return getAlarmCenterUrl({ hash: getAlarmCenterListHash(query), bizId });
}

/**
 * 用于 Vue Router 的 `router.push` / `router.resolve` 入参（命名路由形式）。
 * 旧版 `name: 'event-center'` / `name: 'event-action'` 都映射到新版 `alarm-center`，
 * `event-action` 自动追加 `alarmType: 'action'`。
 */
export function getAlarmCenterRouteLocation(query?: ILegacyAlarmCenterQuery): {
  name: string;
  query: Record<string, any>;
} {
  return {
    name: ALARM_CENTER_ROUTE_NAME,
    query: transformLegacyAlarmQuery(query),
  };
}

/**
 * 根据 hash 拼出完整跳转 URL（含 origin/pathname/bizId）。
 * 与项目原有的 `commOpenUrl` 行为对齐，仅替换 hash 段。
 */
export function getAlarmCenterUrl(opts: { bizId?: number | string; hash?: string } = {}): string {
  const hash = opts.hash ?? ALARM_CENTER_LIST_HASH;
  const bizId = resolveBizId(opts.bizId);
  // if (process.env.NODE_ENV === 'development' && (process.env as any).proxyUrl) {
  //   return `${(process.env as any).proxyUrl}?bizId=${bizId}${hash}`;
  // }
  const { origin, pathname } = window.location;
  return `${origin}${pathname}?bizId=${bizId}${hash}`;
}

/** 在新窗口打开新版告警中心列表页 */
export function openAlarmCenter(
  query?: ILegacyAlarmCenterQuery,
  target = '_blank',
  bizId?: number | string
): null | Window {
  console.info('getAlarmCenterListUrl', getAlarmCenterListUrl(query, bizId));
  return window.open(getAlarmCenterListUrl(query, bizId), target);
}

/** 在新窗口打开新版告警中心详情页 */
export function openAlarmCenterDetail(
  alarmId: number | string,
  query?: ILegacyAlarmCenterQuery,
  target = '_blank',
  bizId?: number | string
): null | Window {
  return window.open(getAlarmCenterDetailUrl(alarmId, query, bizId), target);
}

/**
 * 把"旧版事件中心 URL 参数"转换成"新版告警中心 URL 参数"。
 * 仅做字段映射，不负责 URL 拼接。
 */
export function transformLegacyAlarmQuery(query?: ILegacyAlarmCenterQuery): Record<string, any> {
  if (!query) return {};
  const result: Record<string, any> = {};
  const queryStringParts: string[] = [];
  if (query.queryString != null && query.queryString !== '') {
    queryStringParts.push(String(query.queryString));
  }

  if (query.alertId != null) {
    queryStringParts.push(`id : ${query.alertId}`);
  }
  if (query.actionId != null) {
    queryStringParts.push(`action_id : ${query.actionId}`);
  }
  if (query.collectId != null) {
    queryStringParts.push(`action_id : ${query.collectId}`);
  }
  if (query.metricId != null) {
    queryStringParts.push(`metric : ${query.metricId}`);
  }

  if (query.searchType && !query.alarmType) {
    result.alarmType = query.searchType;
  }

  for (const key of Object.keys(query)) {
    const value = (query as any)[key];
    if (value === undefined) continue;
    if (key === 'queryString') continue;
    if (LEGACY_FIELDS.has(key)) continue;
    if (UNSUPPORTED_FIELDS.has(key) && process.env.NODE_ENV === 'development') {
      console.warn(`[alarm-center-router] 新版告警中心未持久化参数 "${key}"，将仅透传。`);
    }
    result[key] = value;
  }

  if (queryStringParts.length) {
    result.queryString = queryStringParts.join(' and ');
    if (result.filterMode == null) {
      result.filterMode = 'queryString';
    }
  }

  applySpecEventCompat(query, result);
  applyActiveFilterIdCompat(query, result);

  return result;
}

/**
 * 把旧版 `activeFilterId` 转换成新版告警中心的 `quickFilterValue`。
 *
 * 旧版事件中心左侧快捷筛选选中项以单一字符串（如 `NOT_SHIELDED_ABNORMAL`）写入 URL，
 * 新版告警中心则统一通过 `quickFilterValue: [{ key, value }]` 表达，
 * 不同 alarmType 下的分类 key 不同（MINE / STATUS / INCIDENT_LEVEL / action）。
 *
 * 处理规则：
 * 1. activeFilterId 与 alarmType 同名（即旧版 overview 总览项）→ 不下发任何快捷筛选；
 * 2. 调用方已显式传入 `quickFilterValue` → 优先以调用方为准，避免覆盖；
 * 3. 找不到对应分类 → 静默忽略（开发环境打印 warn 提示）。
 */
function applyActiveFilterIdCompat(raw: ILegacyAlarmCenterQuery, result: Record<string, any>): void {
  const activeFilterId = raw.activeFilterId;
  if (!activeFilterId) return;
  if (result.quickFilterValue != null) return;

  const alarmType = (result.alarmType || raw.alarmType || raw.searchType || 'alert') as 'action' | 'alert' | 'incident';
  if (activeFilterId === alarmType) return;

  const key = ACTIVE_FILTER_ID_KEY_MAP[alarmType]?.[activeFilterId];
  if (!key) {
    if (process.env.NODE_ENV === 'development') {
      console.warn(
        `[alarm-center-router] 未识别的 activeFilterId="${activeFilterId}"（alarmType=${alarmType}），已忽略。`
      );
    }
    return;
  }

  result.quickFilterValue = [{ key, value: [activeFilterId] }];
}

/** 同时存在 specEvent + (alertId | collectId) 时，新版改用 alarmId + showDetail 表达 */
function applySpecEventCompat(raw: ILegacyAlarmCenterQuery, result: Record<string, any>): void {
  if (!raw.specEvent) return;
  const targetId = raw.alertId ?? raw.collectId;
  if (targetId == null) return;
  if (result.alarmId == null) result.alarmId = String(targetId);
  if (raw.bizIds != null && result.alarmBizId == null) {
    result.alarmBizId = Array.isArray(raw.bizIds) ? raw.bizIds[0] : raw.bizIds;
  }
  if (result.showDetail == null) result.showDetail = 'true';
}

/** 当前业务 ID（与项目 `commOpenUrl` 保持一致：优先 window.cc_biz_id） */
function resolveBizId(bizId?: number | string): string {
  if (bizId != null && bizId !== '') return String(bizId);
  return String((window as any).cc_biz_id ?? '');
}

/** 把对象序列化成 URL search 字符串（不带 ?，自动 encode） */
function stringifyQuery(query: Record<string, any>): string {
  const parts: string[] = [];
  for (const key of Object.keys(query)) {
    const value = query[key];
    if (value === undefined || value === null || value === '') continue;
    const str = typeof value === 'object' ? JSON.stringify(value) : String(value);
    parts.push(`${encodeURIComponent(key)}=${encodeURIComponent(str)}`);
  }
  return parts.join('&');
}
