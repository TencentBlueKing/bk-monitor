/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 */
import db, { type RetrieveRowEntity } from '../core/db';
import { retrieveRowProjectionService, type RetrieveRowProjection } from '../services/retrieve-row-projection.service';

const DEFAULT_TTL = 30 * 60 * 1000;
const DEFAULT_BATCH_ROWS = 5;
const DEFAULT_BATCH_BYTES = 8 * 1024 * 1024;

const nextIdle = () => new Promise(resolve => setTimeout(resolve, 0));

interface WriteRowsOptions {
  ttl?: number;
  fieldNames?: string[];
  batchRows?: number;
  batchBytes?: number;
}

export class RetrieveRowRepository {
  async replaceRows(queryKey: string, rows: Record<string, any>[], startSeq = 0, options: WriteRowsOptions = {}) {
    const ttl = options.ttl ?? DEFAULT_TTL;
    if (startSeq === 0) {
      await db.retrieveRows.where('queryKey').equals(queryKey).delete();
    }

    return this.writeRows(queryKey, rows, startSeq, ttl, options);
  }

  async appendRows(queryKey: string, rows: Record<string, any>[], startSeq: number, options: WriteRowsOptions = {}) {
    return this.writeRows(queryKey, rows, startSeq, options.ttl ?? DEFAULT_TTL, options);
  }

  async getRowsByKeys(keys: string[]) {
    if (!keys.length) return [];
    const rows = await db.retrieveRows.bulkGet(keys);
    return rows.map(item => item?.row);
  }

  async getEntitiesByKeys(keys: string[]) {
    if (!keys.length) return [];
    return db.retrieveRows.bulkGet(keys);
  }

  async getProjectionsByKeys(keys: string[]): Promise<(RetrieveRowProjection | undefined)[]> {
    if (!keys.length) return [];
    const rows = await db.retrieveRows.bulkGet(keys);
    return rows.map(item => item?.projection);
  }

  async getRowsByQuery(queryKey: string, offset = 0, limit?: number) {
    const entities = await this.getEntitiesByQuery(queryKey, offset, limit);
    return entities.map(item => item.row).filter(Boolean);
  }

  async getProjectionsByQuery(queryKey: string, offset = 0, limit?: number) {
    const entities = await this.getEntitiesByQuery(queryKey, offset, limit);
    return entities.map(item => item.projection).filter(Boolean);
  }

  async getAllRowsByQuery(queryKey: string) {
    return this.getRowsByQuery(queryKey);
  }

  async clearQuery(queryKey: string) {
    await db.retrieveRows.where('queryKey').equals(queryKey).delete();
  }

  async gc(now = Date.now(), options: { excludeQueryKeys?: string[] } = {}) {
    const excludeQueryKeySet = new Set(options.excludeQueryKeys?.filter(Boolean) ?? []);
    if (!excludeQueryKeySet.size) {
      await db.retrieveRows.where('expireAt').below(now).delete();
      return;
    }

    await db.transaction('rw', db.retrieveRows, async () => {
      const expiredRows = await db.retrieveRows.where('expireAt').below(now).toArray();
      const deleteKeys = expiredRows
        .filter(row => !excludeQueryKeySet.has(row.queryKey))
        .map(row => row.key);
      if (deleteKeys.length) {
        await db.retrieveRows.bulkDelete(deleteKeys);
      }
    });
  }

  async getEntitiesByQuery(queryKey: string, offset = 0, limit?: number) {
    if (!queryKey) return [];
    const collection = db.retrieveRows.where('[queryKey+seq]').between(
      [queryKey, offset],
      [queryKey, Number.MAX_SAFE_INTEGER],
    );

    if (typeof limit === 'number') {
      return collection.limit(limit).toArray();
    }

    return collection.toArray();
  }

  private async writeRows(
    queryKey: string,
    rows: Record<string, any>[],
    startSeq: number,
    ttl: number,
    options: WriteRowsOptions,
  ) {
    const now = Date.now();
    const expireAt = now + ttl;
    const keys: string[] = [];
    let batch: RetrieveRowEntity[] = [];
    let batchBytes = 0;
    const maxBatchRows = options.batchRows ?? DEFAULT_BATCH_ROWS;
    const maxBatchBytes = options.batchBytes ?? DEFAULT_BATCH_BYTES;

    const flush = async () => {
      if (!batch.length) return;
      await db.retrieveRows.bulkPut(batch);
      batch = [];
      batchBytes = 0;
      await nextIdle();
    };

    for (let index = 0; index < rows.length; index++) {
      const seq = startSeq + index;
      const storageValue = retrieveRowProjectionService.createStorageValue(rows[index], queryKey, seq, options.fieldNames ?? []);
      const entity: RetrieveRowEntity = {
        key: `${queryKey}:${seq}`,
        queryKey,
        seq,
        row: storageValue.row,
        projection: storageValue.projection,
        bytes: storageValue.bytes,
        createdAt: now,
        expireAt,
      };
      keys.push(entity.key);
      batch.push(entity);
      batchBytes += entity.bytes ?? 0;

      if (batch.length >= maxBatchRows || batchBytes >= maxBatchBytes) {
        await flush();
      }
    }

    await flush();
    return keys;
  }
}

export const retrieveRowRepository = new RetrieveRowRepository();
