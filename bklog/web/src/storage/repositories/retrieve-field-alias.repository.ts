/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 */
import db, { type RetrieveFieldAliasConfigEntity } from '../core/db';
import { storageHealthService } from '../services/storage-health.service';
import { normalizeStorageValue } from '../utils/normalize-storage-value';

const DEFAULT_TTL = 7 * 24 * 60 * 60 * 1000;

export class RetrieveFieldAliasRepository {
  async setAliasConfig(
    scope: string,
    data: Omit<RetrieveFieldAliasConfigEntity, 'createdAt' | 'expireAt' | 'key' | 'scope' | 'updatedAt'>,
    ttl = DEFAULT_TTL,
  ) {
    if (!scope || !(await storageHealthService.ensureIndexedDBUsable())) return;
    const now = Date.now();
    try {
      const old = await db.retrieveFieldAliasConfigs.get(scope);
      await db.retrieveFieldAliasConfigs.put({
        key: scope,
        scope,
        ...normalizeStorageValue(data),
        createdAt: old?.createdAt ?? now,
        updatedAt: now,
        expireAt: now + ttl,
      });
    } catch (error) {
      storageHealthService.resetIndexedDBUsable();
      console.warn('[retrieve-field-alias] set alias config failed', scope, error);
    }
  }

  async getAliasConfig(scope: string): Promise<RetrieveFieldAliasConfigEntity | undefined> {
    if (!scope || !(await storageHealthService.ensureIndexedDBUsable())) return undefined;
    try {
      const entity = await db.retrieveFieldAliasConfigs.get(scope);
      if (!entity) return undefined;
      if (entity.expireAt && entity.expireAt < Date.now()) {
        await db.retrieveFieldAliasConfigs.delete(scope);
        return undefined;
      }
      return entity;
    } catch (error) {
      storageHealthService.resetIndexedDBUsable();
      console.warn('[retrieve-field-alias] get alias config failed', scope, error);
      return undefined;
    }
  }

  async clearAliasConfig(scope: string) {
    if (!scope || !(await storageHealthService.ensureIndexedDBUsable())) return;
    try {
      await db.retrieveFieldAliasConfigs.delete(scope);
    } catch (error) {
      storageHealthService.resetIndexedDBUsable();
      console.warn('[retrieve-field-alias] clear alias config failed', scope, error);
    }
  }

  async gc(now = Date.now()) {
    if (!(await storageHealthService.ensureIndexedDBUsable())) return;
    try {
      await db.retrieveFieldAliasConfigs.where('expireAt').below(now).delete();
    } catch (error) {
      storageHealthService.resetIndexedDBUsable();
      console.warn('[retrieve-field-alias] gc failed', error);
    }
  }
}

export const retrieveFieldAliasRepository = new RetrieveFieldAliasRepository();
export type { RetrieveFieldAliasConfigEntity };
