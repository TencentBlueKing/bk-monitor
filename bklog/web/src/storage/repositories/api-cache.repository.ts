/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 */
import db, { type ApiCacheEntity } from '../core/db';

const DEFAULT_TTL = 30 * 60 * 1000;

export class ApiCacheRepository {
  async set(key: string, data: any, meta: Record<string, any> = {}, ttl = DEFAULT_TTL) {
    const now = Date.now();
    await db.apiCaches.put({
      key,
      data,
      meta,
      updatedAt: now,
      expireAt: now + ttl,
    });
  }

  async get<T = any>(key: string): Promise<T | undefined> {
    const item = await db.apiCaches.get(key);
    if (!item) return undefined;
    if (item.expireAt && item.expireAt < Date.now()) {
      await db.apiCaches.delete(key);
      return undefined;
    }
    return item.data as T;
  }

  async remove(key: string) {
    await db.apiCaches.delete(key);
  }

  async gc() {
    await db.apiCaches.where('expireAt').below(Date.now()).delete();
  }
}

export const apiCacheRepository = new ApiCacheRepository();
export type { ApiCacheEntity };
