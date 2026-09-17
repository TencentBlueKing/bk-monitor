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
import type { LocationQuery, LocationQueryRaw } from 'vue-router';

/** 详情页 / 侧滑自有字段，返回列表时去掉，避免污染列表 URL */
const INCIDENT_DETAIL_QUERY_KEYS = new Set(['activeTab', 'fromPage', 'showDetail', 'detailId', 'detailBizId']);

/**
 * 去详情：带上当前列表 query，并标记来源；可选详情 Tab。
 */
export function buildIncidentDetailQuery(
  query: LocationQuery = {},
  extra: { activeTab?: string; from?: number | string; to?: number | string } = {}
): LocationQueryRaw {
  const listQuery = cloneQuery(query);
  if (!listQuery.from && extra.from) {
    listQuery.from = extra.from;
  }
  if (!listQuery.to && extra.to) {
    listQuery.to = extra.to;
  }
  return {
    ...listQuery,
    fromPage: 'alarm-center',
    ...(extra.activeTab ? { activeTab: extra.activeTab } : {}),
  };
}

/**
 * 列表当前 URL query 原样带回（后续新增筛选字段无需改这里）。
 * 仅剔除详情页自己写入的字段。
 */
export function pickIncidentListQuery(query: LocationQuery = {}): LocationQueryRaw {
  const result = cloneQuery(query);
  for (const key of INCIDENT_DETAIL_QUERY_KEYS) {
    delete result[key];
  }
  if (!result.alarmType) {
    result.alarmType = 'incident';
  }
  return result;
}

function cloneQuery(query: LocationQuery = {}): LocationQueryRaw {
  const result: LocationQueryRaw = {};
  for (const [key, value] of Object.entries(query)) {
    if (value == null || value === '') {
      continue;
    }
    result[key] = value;
  }
  return result;
}
