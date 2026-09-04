/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 */

/**
 * 独立 bklog 新开页去掉嵌入布局参数，避免 HeadNav 被 from=monitor / hl=1 隐藏。
 * 监控内跳转走 buildMonitorLogRetrievalUrl，不经过此函数剥离。
 * @param {Record<string, unknown>} query
 * @param {boolean} isMonitorEmbed
 * @returns {Record<string, unknown>}
 */
export function applyIndependentPageLayoutQuery(query, isMonitorEmbed) {
  if (!isMonitorEmbed) {
    delete query.from;
    delete query.hl;
  }
  return query;
}

/**
 * 监控 iframe / 组件内取顶层 host。跨域读 top 失败时回退 MONITOR_URL。
 * @returns {string}
 */
export function getMonitorTopOrigin() {
  try {
    const topLocation = window.top?.location;
    if (topLocation?.host) {
      return `${topLocation.protocol}//${topLocation.host}`.replace(/\/$/, '');
    }
  } catch {
    // 跨域 iframe 无法读 window.top.location
  }
  return String(window.MONITOR_URL || '').replace(/\/$/, '');
}

function toQueryValue(value) {
  if (value === undefined || value === null || value === '') {
    return '';
  }
  if (typeof value === 'object') {
    return JSON.stringify(value);
  }
  return String(value);
}

function toQueryString(query) {
  return Object.entries(query)
    .filter(([, value]) => value !== undefined && value !== null && value !== '')
    .map(([key, value]) => `${encodeURIComponent(key)}=${encodeURIComponent(toQueryValue(value))}`)
    .join('&');
}

/**
 * 监控内新开 Tab：落在监控 #/log-retrieval，而不是日志平台 /retrieve。
 * {origin}/?bizId={bizId}#/log-retrieval?indexId=&from=monitor&bizId=&spaceUid=&search_mode=&addition=&pid=&...
 * @param {{
 *   bizId?: string | number,
 *   spaceUid?: string,
 *   indexId?: string | number,
 *   pid?: unknown,
 *   query?: Record<string, unknown>,
 *   origin?: string,
 * }} options
 * @returns {string}
 */
export function buildMonitorLogRetrievalUrl(options = {}) {
  const { bizId, spaceUid, indexId, pid, query = {}, origin } = options;
  const host = (origin || getMonitorTopOrigin()).replace(/\/$/, '');
  const hashQuery = {
    ...query,
    indexId: indexId ?? query.indexId,
    from: 'monitor',
    bizId: bizId ?? query.bizId,
    spaceUid: spaceUid ?? query.spaceUid,
    pid: pid ?? query.pid,
  };
  const search = toQueryString({ bizId: hashQuery.bizId });
  const hash = toQueryString(hashQuery);
  return `${host}/?${search}#/log-retrieval${hash ? `?${hash}` : ''}`;
}

export function isMonitorEmbedContext(query = {}) {
  return Boolean(window.__IS_MONITOR_COMPONENT__) || query.from === 'monitor';
}
