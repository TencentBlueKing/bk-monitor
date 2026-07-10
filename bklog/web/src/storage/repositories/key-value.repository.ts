/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 */
import db, { type KeyValueEntity } from '../core/db';
import { storageHealthService } from '../services/storage-health.service';
import { normalizeStorageValue } from '../utils/normalize-storage-value';

const DEFAULT_TTL = 7 * 24 * 60 * 60 * 1000;

export class KeyValueRepository {
  async set(key: string, value: any, ttl = DEFAULT_TTL) {
    if (!await storageHealthService.ensureIndexedDBUsable()) return;
    const now = Date.now();
    try {
      await db.keyValues.put({
        key,
        value: normalizeStorageValue(value),
        updatedAt: now,
        expireAt: now + ttl,
      });
    } catch (error) {
      storageHealthService.resetIndexedDBUsable();
      console.warn('[key-value-cache] set failed', key, error);
    }
  }

  async get<T = any>(key: string): Promise<T | undefined> {
    if (!await storageHealthService.ensureIndexedDBUsable()) return undefined;
    try {
      const item = await db.keyValues.get(key);
      if (!item) return undefined;
      if (item.expireAt && item.expireAt < Date.now()) {
        await db.keyValues.delete(key);
        return undefined;
      }
      return item.value as T;
    } catch (error) {
      storageHealthService.resetIndexedDBUsable();
      console.warn('[key-value-cache] get failed', key, error);
      return undefined;
    }
  }

  async remove(key: string) {
    if (!await storageHealthService.ensureIndexedDBUsable()) return;
    try {
      await db.keyValues.delete(key);
    } catch (error) {
      storageHealthService.resetIndexedDBUsable();
      console.warn('[key-value-cache] remove failed', key, error);
    }
  }

  async gc() {
    if (!await storageHealthService.ensureIndexedDBUsable()) return;
    try {
      await db.keyValues.where('expireAt').below(Date.now()).delete();
    } catch (error) {
      storageHealthService.resetIndexedDBUsable();
      console.warn('[key-value-cache] gc failed', error);
    }
  }
}

export const keyValueRepository = new KeyValueRepository();
export type { KeyValueEntity };
