/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 */
import db, { type ApiCacheEntity } from '../core/db';
import { storageHealthService } from '../services/storage-health.service';

const DEFAULT_TTL = 30 * 60 * 1000;

export class ApiCacheRepository {
  async set(key: string, data: any, meta: Record<string, any> = {}, ttl = DEFAULT_TTL) {
    if (!await storageHealthService.ensureIndexedDBUsable()) return;
    const now = Date.now();
    try {
      await db.apiCaches.put({
        key,
        data,
        meta,
        updatedAt: now,
        expireAt: now + ttl,
      });
    } catch (error) {
      storageHealthService.resetIndexedDBUsable();
      console.warn('[api-cache] set failed', key, error);
    }
  }

  async get<T = any>(key: string): Promise<T | undefined> {
    if (!await storageHealthService.ensureIndexedDBUsable()) return undefined;
    try {
      const item = await db.apiCaches.get(key);
      if (!item) return undefined;
      if (item.expireAt && item.expireAt < Date.now()) {
        await db.apiCaches.delete(key);
        return undefined;
      }
      return item.data as T;
    } catch (error) {
      storageHealthService.resetIndexedDBUsable();
      console.warn('[api-cache] get failed', key, error);
      return undefined;
    }
  }

  async remove(key: string) {
    if (!await storageHealthService.ensureIndexedDBUsable()) return;
    try {
      await db.apiCaches.delete(key);
    } catch (error) {
      storageHealthService.resetIndexedDBUsable();
      console.warn('[api-cache] remove failed', key, error);
    }
  }

  async gc() {
    if (!await storageHealthService.ensureIndexedDBUsable()) return;
    try {
      await db.apiCaches.where('expireAt').below(Date.now()).delete();
    } catch (error) {
      storageHealthService.resetIndexedDBUsable();
      console.warn('[api-cache] gc failed', error);
    }
  }
}

export const apiCacheRepository = new ApiCacheRepository();
export type { ApiCacheEntity };
