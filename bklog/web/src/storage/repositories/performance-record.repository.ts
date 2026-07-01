/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 */
import db, { type PerformanceRecordEntity } from '../core/db';
import { storageHealthService } from '../services/storage-health.service';

const DEFAULT_LIMIT = 10000;
const MAX_SAFE_DEPTH = 8;
const MAX_SAFE_ARRAY_LENGTH = 200;
const MAX_SAFE_STRING_LENGTH = 4000;

const toCloneableValue = (value: unknown, depth = 0, seen = new WeakSet<object>()): unknown => {
  if (value === null || value === undefined) return value;

  const valueType = typeof value;
  if (valueType === 'function') {
    return `[function:${value.name || 'anonymous'}]`;
  }
  if (valueType === 'symbol') {
    return value.toString();
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
