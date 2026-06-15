/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 */
import db, { type KeyValueEntity } from '../core/db';

const DEFAULT_TTL = 7 * 24 * 60 * 60 * 1000;

export class KeyValueRepository {
  async set(key: string, value: any, ttl = DEFAULT_TTL) {
    const now = Date.now();
    await db.keyValues.put({
      key,
      value,
      updatedAt: now,
      expireAt: now + ttl,
    });
  }

  async get<T = any>(key: string): Promise<T | undefined> {
    const item = await db.keyValues.get(key);
    if (!item) return undefined;
    if (item.expireAt && item.expireAt < Date.now()) {
      await db.keyValues.delete(key);
      return undefined;
    }
    return item.value as T;
  }

  async remove(key: string) {
    await db.keyValues.delete(key);
  }

  async gc() {
    await db.keyValues.where('expireAt').below(Date.now()).delete();
  }
}

export const keyValueRepository = new KeyValueRepository();
export type { KeyValueEntity };
