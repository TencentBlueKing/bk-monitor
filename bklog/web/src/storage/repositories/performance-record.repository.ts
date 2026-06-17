/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 */
import db, { type PerformanceRecordEntity } from '../core/db';
import { storageHealthService } from '../services/storage-health.service';

const DEFAULT_LIMIT = 10000;

export class PerformanceRecordRepository {
  async bulkAdd(records: PerformanceRecordEntity[]) {
    if (!records.length || !await storageHealthService.ensureIndexedDBUsable()) return;
    try {
      await db.performanceRecords.bulkAdd(records);
    } catch (error) {
      storageHealthService.resetIndexedDBUsable();
      console.warn('[performance-monitor] bulk add failed', error);
    }
  }

  async list(sessionId?: string, limit = DEFAULT_LIMIT) {
    if (!await storageHealthService.ensureIndexedDBUsable()) return [];
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
    if (!await storageHealthService.ensureIndexedDBUsable()) return;
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
    if (!await storageHealthService.ensureIndexedDBUsable()) return;
    try {
      await db.performanceRecords.where('timestamp').below(Date.now() - maxAge).delete();
    } catch (error) {
      storageHealthService.resetIndexedDBUsable();
      console.warn('[performance-monitor] gc failed', error);
    }
  }
}

export const performanceRecordRepository = new PerformanceRecordRepository();
export type { PerformanceRecordEntity };
