/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 * License for 蓝鲸智云PaaS平台 (BlueKing PaaS):
 * ---------------------------------------------------
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
 * documentation files (the "Software"), to deal in the Software without restriction, including without limitation
 * the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
 * to permit persons to whom the Software is furnished to do so, subject to the following conditions:
 * The above copyright notice and this permission notice shall be included in all copies or substantial portions of
 * the Software.
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
 * THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
 * CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
 * IN THE SOFTWARE.
 */

import db, { type PerformanceRecordEntity } from '../core/db';
import { storageHealthService } from '../services/storage-health.service';
import { isBigNumberValue, normalizeBigNumberForStorage } from '../utils/normalize-storage-value';

const DEFAULT_LIMIT = 10000;
const MAX_SAFE_DEPTH = 8;
const MAX_SAFE_ARRAY_LENGTH = 200;
const MAX_SAFE_STRING_LENGTH = 4000;

const toCloneableValue = (value: any, depth = 0, seen = new WeakSet<object>()): unknown => {
  if (value === null || value === undefined) return value;

  const valueType = typeof value;
  if (valueType === 'function') {
    return `[function:${value.name || 'anonymous'}]`;
  }
  if (valueType === 'symbol') {
    return value.toString();
  }
  if (isBigNumberValue(value)) {
    return normalizeBigNumberForStorage(value);
  }

  if (valueType !== 'object') {
    if (valueType === 'string' && value.length > MAX_SAFE_STRING_LENGTH) {
      return `${value.slice(0, MAX_SAFE_STRING_LENGTH)}...<truncated:${value.length}>`;
    }
    return value;
  }

  if (depth >= MAX_SAFE_DEPTH) {
    return Array.isArray(value) ? `[array:${value.length}]` : `[object:${value.constructor?.name || 'Object'}]`;
  }

  if (seen.has(value)) {
    return '[circular]';
  }
  seen.add(value);

  if (value instanceof Date) {
    return value.toISOString();
  }
  if (value instanceof Error) {
    return {
      message: value.message,
      name: value.name,
      stack: value.stack,
    };
  }
  if (typeof Element !== 'undefined' && value instanceof Element) {
    return `[element:${value.tagName.toLowerCase()}${value.id ? `#${value.id}` : ''}]`;
  }
  if (typeof Window !== 'undefined' && value instanceof Window) {
    return '[window]';
  }
  if (typeof Document !== 'undefined' && value instanceof Document) {
    return '[document]';
  }
  if (Array.isArray(value)) {
    return value.slice(0, MAX_SAFE_ARRAY_LENGTH).map(item => toCloneableValue(item, depth + 1, seen));
  }
  if (value instanceof Map) {
    return Array.from(value.entries())
      .slice(0, MAX_SAFE_ARRAY_LENGTH)
      .map(([key, item]) => [toCloneableValue(key, depth + 1, seen), toCloneableValue(item, depth + 1, seen)]);
  }
  if (value instanceof Set) {
    return Array.from(value.values())
      .slice(0, MAX_SAFE_ARRAY_LENGTH)
      .map(item => toCloneableValue(item, depth + 1, seen));
  }

  const source = value as Record<string, unknown>;
  return Object.keys(value).reduce(
    (output, key) => {
      output[key] = toCloneableValue(source[key], depth + 1, seen);
      return output;
    },
    {} as Record<string, unknown>,
  );
};

const toCloneableRecord = (record: PerformanceRecordEntity): PerformanceRecordEntity => ({
  ...record,
  data: toCloneableValue(record.data),
});

export class PerformanceRecordRepository {
  async bulkAdd(records: PerformanceRecordEntity[]) {
    if (!records.length || !(await storageHealthService.ensureIndexedDBUsable())) return;
    try {
      await db.performanceRecords.bulkAdd(records.map(toCloneableRecord));
    } catch (error) {
      storageHealthService.resetIndexedDBUsable();
      console.warn('[performance-monitor] bulk add failed', error);
    }
  }

  async list(sessionId?: string, limit = DEFAULT_LIMIT) {
    if (!(await storageHealthService.ensureIndexedDBUsable())) return [];
    try {
      const table = db.performanceRecords;
      const rows = sessionId
        ? await table.where('sessionId').equals(sessionId).reverse().limit(limit).toArray()
        : await table.orderBy('timestamp').reverse().limit(limit).toArray();
      return rows.reverse();
    } catch (error) {
      storageHealthService.resetIndexedDBUsable();
      console.warn('[performance-monitor] list failed', error);
      return [];
    }
  }

  async count(sessionId?: string) {
    if (!(await storageHealthService.ensureIndexedDBUsable())) return 0;
    try {
      return sessionId
        ? await db.performanceRecords.where('sessionId').equals(sessionId).count()
        : await db.performanceRecords.count();
    } catch (error) {
      storageHealthService.resetIndexedDBUsable();
      console.warn('[performance-monitor] count failed', error);
      return 0;
    }
  }

  async listRecent(options: {
    sessionId?: string;
    tabId?: string;
    since?: number;
    limit?: number;
    types?: string[];
  } = {}) {
    if (!(await storageHealthService.ensureIndexedDBUsable())) return [];
    const limit = Math.min(Math.max(options.limit || 1500, 1), 4000);
    const since = options.since || Date.now() - 30 * 60 * 1000;
    const typeSet = options.types?.length ? new Set(options.types) : null;
    try {
      const fetchLimit = typeSet || options.tabId
        ? Math.min(limit * 6, 10000)
        : Math.min(limit * 3, 8000);
      const raw = await db.performanceRecords
        .where('timestamp')
        .aboveOrEqual(since)
        .reverse()
        .limit(fetchLimit)
        .toArray();
      const rows = raw.filter((record) => {
        if (options.sessionId && record.sessionId !== options.sessionId) return false;
        if (options.tabId && record.tabId !== options.tabId) return false;
        if (typeSet && !typeSet.has(record.type)) return false;
        return true;
      });
      return rows.slice(0, limit).reverse();
    } catch (error) {
      storageHealthService.resetIndexedDBUsable();
      console.warn('[performance-monitor] listRecent failed', error);
      return [];
    }
  }

  async clear(sessionId?: string) {
    if (!(await storageHealthService.ensureIndexedDBUsable())) return;
    try {
      if (sessionId) {
        await db.performanceRecords.where('sessionId').equals(sessionId).delete();
        return;
      }
      await db.performanceRecords.clear();
    } catch (error) {
      storageHealthService.resetIndexedDBUsable();
      console.warn('[performance-monitor] clear failed', error);
    }
  }

  async gc(maxAge = 24 * 60 * 60 * 1000) {
    if (!(await storageHealthService.ensureIndexedDBUsable())) return;
    try {
      await db.performanceRecords
        .where('timestamp')
        .below(Date.now() - maxAge)
        .delete();
    } catch (error) {
      storageHealthService.resetIndexedDBUsable();
      console.warn('[performance-monitor] gc failed', error);
    }
  }
}

export const performanceRecordRepository = new PerformanceRecordRepository();
export type { PerformanceRecordEntity };
