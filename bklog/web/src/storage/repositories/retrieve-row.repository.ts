/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 */
import db, { type RetrieveRowEntity } from '../core/db';
import { retrieveRowProjectionService, type RetrieveRowProjection } from '../services/retrieve-row-projection.service';
import { createRetrieveRowRenderMeta, type RetrieveRowRenderMeta } from '../utils/retrieve-render-meta';

const DEFAULT_TTL = 30 * 60 * 1000;
const DEFAULT_BATCH_ROWS = 5;
const DEFAULT_BATCH_BYTES = 8 * 1024 * 1024;

const nextIdle = () => new Promise(resolve => setTimeout(resolve, 0));

const hasMark = (value: any) => typeof value === 'string' && /<\/?mark>/i.test(value);

const isPlainObject = (value: any) => Object.prototype.toString.call(value) === '[object Object]';

const collectMarkedFields = (value: any, prefix = '', output: Record<string, any> = {}) => {
  if (hasMark(value) && prefix) {
    output[prefix] = value;
    return output;
  }

  if (!isPlainObject(value)) return output;

  Object.keys(value).forEach((key) => {
    if (key === '__highlight') return;
    const fieldName = prefix ? `${prefix}.${key}` : key;
    collectMarkedFields(value[key], fieldName, output);
  });

  return output;
};

const collectHighlightFields = (rawRow: Record<string, any> = {}) => {
  const output: Record<string, any> = {};
  const highlight = rawRow.__highlight;
  if (!isPlainObject(highlight)) return output;

  Object.keys(highlight).forEach((fieldName) => {
    const value = Array.isArray(highlight[fieldName])
      ? highlight[fieldName][0]
      : highlight[fieldName];
    if (hasMark(value)) {
      output[fieldName] = value;
    }
  });

  return output;
};

const setOverlayValue = (row: Record<string, any>, fieldName: string, value: any) => {
  if (!fieldName.includes('.') || Object.prototype.hasOwnProperty.call(row, fieldName)) {
    row[fieldName] = value;
    return row;
  }

  const path = fieldName.split('.');
  const rootKey = path[0];
  if (!isPlainObject(row[rootKey])) {
    row[fieldName] = value;
    return row;
  }

  row[rootKey] = { ...row[rootKey] };
  let current = row[rootKey];
  for (let index = 1; index < path.length - 1; index++) {
    const key = path[index];
    if (!isPlainObject(current[key])) {
      current[path.slice(index).join('.')] = value;
      return row;
    }
    current[key] = { ...current[key] };
    current = current[key];
  }

  current[path[path.length - 1]] = value;
  return row;
};

interface RenderOverlayField {
  renderValue: any;
}

interface RetrieveRowRenderOverlay {
  fields: Record<string, RenderOverlayField>;
  hasHighlight: boolean;
}

interface WriteRowsOptions {
  ttl?: number;
  fieldNames?: string[];
  batchRows?: number;
  batchBytes?: number;
  renderRows?: Record<string, any>[];
  renderMetas?: RetrieveRowRenderMeta[];
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

  async getRenderRowsByKeys(keys: string[]) {
    if (!keys.length) return [];
    const entities = await db.retrieveRows.bulkGet(keys);
    return entities.map(entity => this.applyRenderOverlay(entity));
  }

  async getRenderMetasByKeys(keys: string[]) {
    if (!keys.length) return [];
    const entities = await db.retrieveRows.bulkGet(keys);
    return entities.map(entity => entity?.renderMeta);
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
      const renderOverlay = this.createRenderOverlay(storageValue.row, options.renderRows?.[index]);
      const entity: RetrieveRowEntity = {
        key: `${queryKey}:${seq}`,
        queryKey,
        seq,
        row: storageValue.row,
        renderOverlay,
        renderMeta: options.renderMetas?.[index] || createRetrieveRowRenderMeta(storageValue.row, options.renderRows?.[index]),
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

  private createRenderOverlay(rawRow: Record<string, any>, renderRow?: Record<string, any>): RetrieveRowRenderOverlay | undefined {
    if (!rawRow || (!renderRow && !rawRow.__highlight)) return undefined;
    const fields: Record<string, RenderOverlayField> = {};

    const markedFields = {
      ...collectMarkedFields(renderRow),
      ...collectHighlightFields(rawRow),
    };
    Object.keys(markedFields).forEach((fieldName) => {
      const renderValue = markedFields[fieldName];
      if (!hasMark(renderValue)) return;
      fields[fieldName] = { renderValue };
    });

    return Object.keys(fields).length ? { fields, hasHighlight: true } : undefined;
  }

  applyRenderOverlay(entity?: RetrieveRowEntity) {
    if (!entity?.row) return undefined;
    const overlay = entity.renderOverlay;
    if (!overlay?.fields || !Object.keys(overlay.fields).length) return entity.row;

    return Object.keys(overlay.fields).reduce(
      (row, fieldName) => setOverlayValue(row, fieldName, overlay.fields[fieldName].renderValue),
      { ...entity.row },
    );
  }
}

export const retrieveRowRepository = new RetrieveRowRepository();
