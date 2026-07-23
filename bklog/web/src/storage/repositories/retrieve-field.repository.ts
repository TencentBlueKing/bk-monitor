/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 */
import db, { type RetrieveFieldMetaEntity, type RetrieveFieldWidthEntity } from '../core/db';
import { storageHealthService } from '../services/storage-health.service';
import { normalizeStorageValue } from '../utils/normalize-storage-value';

const DEFAULT_TTL = 7 * 24 * 60 * 60 * 1000;

const getWidthKey = (scope: string, fieldName: string) => `${scope}:${fieldName}`;

export class RetrieveFieldRepository {
  async setMeta(
    scope: string,
    data: Omit<RetrieveFieldMetaEntity, 'createdAt' | 'expireAt' | 'key' | 'scope' | 'updatedAt'>,
    ttl = DEFAULT_TTL,
  ) {
    if (!scope || !(await storageHealthService.ensureIndexedDBUsable())) return;
    const now = Date.now();
    try {
      const old = await db.retrieveFieldMetas.get(scope);
      await db.retrieveFieldMetas.put({
        key: scope,
        scope,
        ...normalizeStorageValue(data),
        createdAt: old?.createdAt ?? now,
        updatedAt: now,
        expireAt: now + ttl,
      });
    } catch (error) {
      storageHealthService.resetIndexedDBUsable();
      console.warn('[retrieve-field] set meta failed', scope, error);
    }
  }

  async getMeta(scope: string): Promise<RetrieveFieldMetaEntity | undefined> {
    if (!scope || !(await storageHealthService.ensureIndexedDBUsable())) return undefined;
    try {
      const entity = await db.retrieveFieldMetas.get(scope);
      if (!entity) return undefined;
      if (entity.expireAt && entity.expireAt < Date.now()) {
        await db.retrieveFieldMetas.delete(scope);
        return undefined;
      }
      return entity;
    } catch (error) {
      storageHealthService.resetIndexedDBUsable();
      console.warn('[retrieve-field] get meta failed', scope, error);
      return undefined;
    }
  }

  async clearMeta(scope: string) {
    if (!scope || !(await storageHealthService.ensureIndexedDBUsable())) return;
    try {
      await db.retrieveFieldMetas.delete(scope);
    } catch (error) {
      storageHealthService.resetIndexedDBUsable();
      console.warn('[retrieve-field] clear meta failed', scope, error);
    }
  }

  async setWidths(scope: string, widths: Record<string, Partial<RetrieveFieldWidthEntity>>, ttl = DEFAULT_TTL) {
    if (!scope || !widths || !(await storageHealthService.ensureIndexedDBUsable())) return;
    const now = Date.now();
    const fieldNames = Object.keys(widths);
    if (!fieldNames.length) return;
    const keys = fieldNames.map(fieldName => getWidthKey(scope, fieldName));

    try {
      const oldRows = await db.retrieveFieldWidths.bulkGet(keys);
      const oldMap = oldRows.reduce(
        (output, row) => {
          if (row) output[row.fieldName] = row;
          return output;
        },
        {} as Record<string, RetrieveFieldWidthEntity>,
      );
      const rows = fieldNames.map(fieldName => ({
        ...(oldMap[fieldName] ?? {}),
        key: getWidthKey(scope, fieldName),
        scope,
        fieldName,
        ...normalizeStorageValue(widths[fieldName]),
        updatedAt: now,
        expireAt: now + ttl,
      }));
      await db.retrieveFieldWidths.bulkPut(rows as RetrieveFieldWidthEntity[]);
    } catch (error) {
      storageHealthService.resetIndexedDBUsable();
      console.warn('[retrieve-field] set widths failed', scope, error);
    }
  }

  async getWidths(scope: string): Promise<Record<string, RetrieveFieldWidthEntity>> {
    if (!scope || !(await storageHealthService.ensureIndexedDBUsable())) return {};
    try {
      const rows = await db.retrieveFieldWidths.where('scope').equals(scope).toArray();
      const now = Date.now();
      const expiredKeys = rows.filter(row => row.expireAt && row.expireAt < now).map(row => row.key);
      if (expiredKeys.length) {
        await db.retrieveFieldWidths.bulkDelete(expiredKeys);
      }
      return rows
        .filter(row => !expiredKeys.includes(row.key))
        .reduce(
          (output, row) => {
            output[row.fieldName] = row;
            return output;
          },
          {} as Record<string, RetrieveFieldWidthEntity>,
        );
    } catch (error) {
      storageHealthService.resetIndexedDBUsable();
      console.warn('[retrieve-field] get widths failed', scope, error);
      return {};
    }
  }

  async clearWidths(scope: string) {
    if (!scope || !(await storageHealthService.ensureIndexedDBUsable())) return;
    try {
      await db.retrieveFieldWidths.where('scope').equals(scope).delete();
    } catch (error) {
      storageHealthService.resetIndexedDBUsable();
      console.warn('[retrieve-field] clear widths failed', scope, error);
    }
  }

  async gc(now = Date.now()) {
    if (!(await storageHealthService.ensureIndexedDBUsable())) return;
    try {
      await Promise.all([
        db.retrieveFieldMetas.where('expireAt').below(now).delete(),
        db.retrieveFieldWidths.where('expireAt').below(now).delete(),
      ]);
    } catch (error) {
      storageHealthService.resetIndexedDBUsable();
      console.warn('[retrieve-field] gc failed', error);
    }
  }
}

export const retrieveFieldRepository = new RetrieveFieldRepository();
export type { RetrieveFieldMetaEntity, RetrieveFieldWidthEntity };
