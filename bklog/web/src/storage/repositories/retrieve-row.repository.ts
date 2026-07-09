/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 */
import db, { type RetrieveRowEntity } from '../core/db';
import { estimateValueBytes } from '../services/retrieve-row-projection.service';
import {
  createRetrieveRowRenderMeta,
  DEFAULT_HIGHLIGHT_FIELD,
  type RetrieveRowRenderMeta,
} from '../utils/retrieve-render-meta';

const DEFAULT_TTL = 30 * 60 * 1000;
const DEFAULT_BATCH_ROWS = 10;
const DEFAULT_BATCH_BYTES = 8 * 1024 * 1024;
const ROW_YIELD_INTERVAL = 5;

const nextIdle = () => new Promise(resolve => setTimeout(resolve, 0));

const hasMark = (value: any) => typeof value === 'string' && /<\/?mark>/i.test(value);

const isPlainObject = (value: any) => Object.prototype.toString.call(value) === '[object Object]';

const collectMarkedFields = (
  value: any,
  prefix = '',
  output: Record<string, any> = {},
  highlightField = DEFAULT_HIGHLIGHT_FIELD,
) => {
  if (hasMark(value) && prefix) {
    output[prefix] = value;
    return output;
  }

  if (!isPlainObject(value)) return output;

  Object.keys(value).forEach(key => {
    if (key === highlightField) return;
    const fieldName = prefix ? `${prefix}.${key}` : key;
    collectMarkedFields(value[key], fieldName, output, highlightField);
  });

  return output;
};

const collectHighlightFields = (
  rawRow: Record<string, any> | undefined = {},
  highlightField = DEFAULT_HIGHLIGHT_FIELD,
) => {
  const output: Record<string, any> = {};
  const highlight = rawRow[highlightField];
  if (!isPlainObject(highlight)) return output;

  Object.keys(highlight).forEach(fieldName => {
    const value = Array.isArray(highlight[fieldName]) ? highlight[fieldName][0] : highlight[fieldName];
    if (hasMark(value)) {
      output[fieldName] = value;
    }
  });

  return output;
};

const setOverlayValue = (row: Record<string, any>, fieldName: string, value: any) => {
  if (!fieldName.includes('.') || Object.hasOwn(row, fieldName)) {
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

const createHighlightField = () => `${DEFAULT_HIGHLIGHT_FIELD}_${Math.random().toString(36).slice(2, 10)}`;

const hasOwnField = (row: Record<string, any> | undefined, fieldName: string) => !!row && Object.hasOwn(row, fieldName);

const resolveHighlightField = (rawRow: Record<string, any>) => {
  if (hasOwnField(rawRow, DEFAULT_HIGHLIGHT_FIELD)) {
    return createHighlightField();
  }
  return DEFAULT_HIGHLIGHT_FIELD;
};

const normalizeRenderRowHighlightField = (
  renderRow: Record<string, any> | undefined,
  highlightField = DEFAULT_HIGHLIGHT_FIELD,
) => {
  if (!renderRow || highlightField === DEFAULT_HIGHLIGHT_FIELD || !hasOwnField(renderRow, DEFAULT_HIGHLIGHT_FIELD)) {
    return renderRow;
  }

  const nextRenderRow = {
    ...renderRow,
    [highlightField]: renderRow[DEFAULT_HIGHLIGHT_FIELD],
  };
  delete nextRenderRow[DEFAULT_HIGHLIGHT_FIELD];
  return nextRenderRow;
};

const getCopyFieldValue = (row: Record<string, any>, fieldName: string) => {
  if (Object.hasOwn(row, fieldName)) {
    return { exists: true, value: row[fieldName] };
  }

  if (!fieldName.includes('.')) {
    return { exists: false, value: undefined };
  }

  const path = fieldName.split('.');
  let current: any = row;
  for (const key of path) {
    if (!isPlainObject(current) || !Object.hasOwn(current, key)) {
      return { exists: false, value: undefined };
    }
    current = current[key];
  }
  return { exists: true, value: current };
};

const sanitizeCopyRow = (
  row: Record<string, any> | undefined,
  copyExcludedFields: string[] = [],
  includeFields: string[] = [],
) => {
  if (!row) return undefined;
  const excludedFieldSet = new Set(copyExcludedFields);
  const fieldNames = includeFields.length ? includeFields : Object.keys(row);

  return fieldNames.reduce(
    (output, key) => {
      if (excludedFieldSet.has(key)) return output;
      const fieldValue = getCopyFieldValue(row, key);
      if (!fieldValue.exists) return output;
      output[key] = fieldValue.value;
      return output;
    },
    {} as Record<string, any>,
  );
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
  copyExcludedFields?: string[];
}

interface CopyRowsOptions {
  includeFields?: string[];
}

interface StreamWriterOptions extends WriteRowsOptions {
  writeMode?: 'append' | 'replace';
}

export class RetrieveRowStreamWriter {
  private batch: RetrieveRowEntity[] = [];
  private batchBytes = 0;
  private keys: string[] = [];
  private initialized = false;
  private readonly maxBatchRows: number;
  private readonly maxBatchBytes: number;
  private readonly ttl: number;
  private readonly now = Date.now();
  private readonly expireAt: number;

  constructor(
    private readonly repository: RetrieveRowRepository,
    private readonly queryKey: string,
    private readonly startSeq: number,
    private readonly options: StreamWriterOptions = {},
  ) {
    this.maxBatchRows = options.batchRows ?? DEFAULT_BATCH_ROWS;
    this.maxBatchBytes = options.batchBytes ?? DEFAULT_BATCH_BYTES;
    this.ttl = options.ttl ?? DEFAULT_TTL;
    this.expireAt = this.now + this.ttl;
  }

  async init() {
    if (this.initialized) return;
    if ((this.options.writeMode ?? 'replace') === 'replace' && this.startSeq === 0) {
      await db.retrieveRows.where('queryKey').equals(this.queryKey).delete();
    }
    this.initialized = true;
  }

  async appendRow(pageIndex: number, originRow: Record<string, any>, renderRow?: Record<string, any>) {
    await this.init();
    const seq = pageIndex >= this.startSeq ? pageIndex : this.startSeq + pageIndex;
    const entity = this.createEntity(originRow, renderRow, seq);
    this.keys.push(entity.key);
    this.batch.push(entity);
    this.batchBytes += entity.bytes ?? 0;

    if (this.batch.length >= this.maxBatchRows || this.batchBytes >= this.maxBatchBytes) {
      await this.flush();
    } else if (pageIndex % ROW_YIELD_INTERVAL === ROW_YIELD_INTERVAL - 1) {
      await nextIdle();
    }
  }

  async finish() {
    await this.flush();
    return this.keys.filter(Boolean);
  }

  getPartialRowKeys() {
    return this.keys.filter(Boolean);
  }

  private async flush() {
    if (!this.batch.length) return;
    await db.retrieveRows.bulkPut(this.batch);
    this.batch = [];
    this.batchBytes = 0;
    await nextIdle();
  }

  private createEntity(originRow: Record<string, any>, renderRow: Record<string, any> | undefined, seq: number) {
    const highlightField = resolveHighlightField(originRow);
    const normalizedRenderRow = normalizeRenderRowHighlightField(renderRow, highlightField);
    const renderOverlay = this.repository.createRenderOverlay(
      originRow,
      normalizedRenderRow,
      highlightField,
    );

    return {
      key: `${this.queryKey}:${seq}`,
      queryKey: this.queryKey,
      seq,
      row: originRow,
      highlightField,
      copyExcludedFields: this.options.copyExcludedFields ?? [],
      renderOverlay,
      renderMeta: createRetrieveRowRenderMeta(originRow, normalizedRenderRow, {
        fieldNames: this.options.fieldNames,
        highlightField,
      }),
      bytes: estimateValueBytes(originRow),
      createdAt: this.now,
      expireAt: this.expireAt,
    } as RetrieveRowEntity;
  }
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

  createStreamWriter(queryKey: string, startSeq: number, options: StreamWriterOptions = {}) {
    return new RetrieveRowStreamWriter(this, queryKey, startSeq, options);
  }

  async getRowsByKeys(keys: string[]) {
    if (!keys.length) return [];
    const rows = await db.retrieveRows.bulkGet(keys);
    return rows.map(item => item?.row);
  }

  async getCopyRowsByKeys(keys: string[], options: CopyRowsOptions = {}) {
    if (!keys.length) return [];
    const rows = await db.retrieveRows.bulkGet(keys);
    return rows.map(item => sanitizeCopyRow(item?.row, item?.copyExcludedFields, options.includeFields ?? []));
  }

  async getEntitiesByKeys(keys: string[]) {
    if (!keys.length) return [];
    return db.retrieveRows.bulkGet(keys);
  }

  async getRenderRowsByKeys(keys: string[]) {
    if (!keys.length) return [];
    const entities = await db.retrieveRows.bulkGet(keys);
    return entities.map(entity => this.resolveRenderRow(entity));
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
      const deleteKeys = expiredRows.filter(row => !excludeQueryKeySet.has(row.queryKey)).map(row => row.key);
      if (deleteKeys.length) {
        await db.retrieveRows.bulkDelete(deleteKeys);
      }
    });
  }

  async getEntitiesByQuery(queryKey: string, offset = 0, limit?: number) {
    if (!queryKey) return [];
    const collection = db.retrieveRows
      .where('[queryKey+seq]')
      .between([queryKey, offset], [queryKey, Number.MAX_SAFE_INTEGER]);

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
      const highlightField = resolveHighlightField(rows[index]);
      const renderRow = normalizeRenderRowHighlightField(options.renderRows?.[index], highlightField);
      const renderOverlay = this.createRenderOverlay(rows[index], renderRow, highlightField);
      const entity: RetrieveRowEntity = {
        key: `${queryKey}:${seq}`,
        queryKey,
        seq,
        row: rows[index],
        highlightField,
        copyExcludedFields: options.copyExcludedFields ?? [],
        renderOverlay,
        renderMeta:
          options.renderMetas?.[index]
          ?? createRetrieveRowRenderMeta(rows[index], renderRow, {
            fieldNames: options.fieldNames,
            highlightField,
          }),
        bytes: estimateValueBytes(rows[index]),
        createdAt: now,
        expireAt,
      };
      keys.push(entity.key);
      batch.push(entity);
      batchBytes += entity.bytes ?? 0;

      if (batch.length >= maxBatchRows || batchBytes >= maxBatchBytes) {
        await flush();
      } else if (index % ROW_YIELD_INTERVAL === ROW_YIELD_INTERVAL - 1) {
        await nextIdle();
      }
    }

    await flush();
    return keys;
  }

  createRenderOverlay(
    rawRow: Record<string, any>,
    renderRow?: Record<string, any>,
    highlightField = DEFAULT_HIGHLIGHT_FIELD,
  ): RetrieveRowRenderOverlay | undefined {
    if (!rawRow || (!renderRow && !rawRow[highlightField])) return undefined;
    const fields: Record<string, RenderOverlayField> = {};

    const markedFields = {
      ...collectMarkedFields(renderRow, '', {}, highlightField),
      ...collectHighlightFields(rawRow, highlightField),
      ...collectHighlightFields(renderRow, highlightField),
    };
    Object.keys(markedFields).forEach(fieldName => {
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

  /** 表格渲染行：先叠加高亮 overlay，再按字段覆盖 32KB 截断展示文本 */
  resolveRenderRow(entity?: RetrieveRowEntity) {
    if (!entity?.row) return undefined;

    const renderRow = this.applyRenderOverlay(entity);
    const truncatedTextByField = entity.renderMeta?.truncatedTextByField;
    if (!renderRow || !truncatedTextByField || !Object.keys(truncatedTextByField).length) {
      return renderRow;
    }

    return Object.keys(truncatedTextByField).reduce(
      (row, fieldName) => setOverlayValue(row, fieldName, truncatedTextByField[fieldName]),
      { ...renderRow },
    );
  }
}

export const retrieveRowRepository = new RetrieveRowRepository();
