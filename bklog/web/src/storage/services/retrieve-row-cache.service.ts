/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 */
import { retrieveRowRepository } from '../repositories/retrieve-row.repository';
import { createRetrieveRowRenderMeta, type RetrieveRowRenderMeta } from '../utils/retrieve-render-meta';
import { estimateValueBytes, retrieveRowProjectionService, type RetrieveRowProjection } from './retrieve-row-projection.service';
import { storageHealthService } from './storage-health.service';

interface MemoryEntry<T = any> {
  value: T;
  bytes: number;
}

interface RenderMemoryEntry extends MemoryEntry<Record<string, any>> {
  renderMeta?: RetrieveRowRenderMeta;
}

interface WriteOptions {
  fieldNames?: string[];
  renderRows?: Record<string, any>[];
  renderMetas?: RetrieveRowRenderMeta[];
}

export class RetrieveRowCacheService {
  private rowMemory = new Map<string, RenderMemoryEntry>();
  private projectionMemory = new Map<string, MemoryEntry<RetrieveRowProjection>>();
  private volatileRows = new Map<string, Record<string, any>>();
  private volatileProjections = new Map<string, RetrieveRowProjection>();
  private maxRowMemoryBytes = 24 * 1024 * 1024;
  private maxProjectionMemoryBytes = 8 * 1024 * 1024;
  private rowMemoryBytes = 0;
  private projectionMemoryBytes = 0;

  createQueryKey(params: Record<string, any>) {
    const seed = JSON.stringify(params ?? {});
    let hash = 0;
    for (let i = 0; i < seed.length; i++) {
      hash = (hash * 31 + seed.charCodeAt(i)) | 0;
    }

    const randomId = typeof crypto !== 'undefined' && crypto.randomUUID
      ? crypto.randomUUID()
      : Math.random().toString(16).slice(2);

    return `retrieve:${Date.now()}:${Math.abs(hash)}:${randomId}`;
  }

  async replaceRows(queryKey: string, rows: Record<string, any>[], options: WriteOptions = {}) {
    this.clearMemory();
    const keys = this.createRowKeys(queryKey, rows.length, 0);
    try {
      await retrieveRowRepository.replaceRows(queryKey, rows, 0, options);
      this.rememberRows(keys, rows, options.fieldNames, false, options.renderMetas);
      retrieveRowRepository.gc().catch((error) => {
        console.warn('[retrieve-row-cache] gc failed', error);
      });
      return keys;
    } catch (error) {
      storageHealthService.resetIndexedDBUsable();
      storageHealthService.notifyIndexedDBFallback();
      console.warn('[retrieve-row-cache] replace rows failed, fallback to volatile memory', error);
      this.rememberRows(keys, rows, options.fieldNames, true, options.renderMetas);
      return keys;
    }
  }

  async appendRows(queryKey: string, rows: Record<string, any>[], startSeq: number, options: WriteOptions = {}) {
    const keys = this.createRowKeys(queryKey, rows.length, startSeq);
    try {
      await retrieveRowRepository.appendRows(queryKey, rows, startSeq, options);
      this.rememberRows(keys, rows, options.fieldNames, false, options.renderMetas);
      return keys;
    } catch (error) {
      storageHealthService.resetIndexedDBUsable();
      storageHealthService.notifyIndexedDBFallback();
      console.warn('[retrieve-row-cache] append rows failed, fallback to volatile memory', error);
      this.rememberRows(keys, rows, options.fieldNames, true, options.renderMetas);
      return keys;
    }
  }

  getMemoryRows(keys: string[]) {
    return keys.map(key => this.rowMemory.get(key)?.value).filter(Boolean);
  }

  async getRenderRows(keys: string[]) {
    const entries = await this.getRenderEntries(keys);
    return entries.map(entry => entry?.row).filter(Boolean);
  }

  async getRenderEntries(keys: string[]) {
    if (!keys.length) return [];
    try {
      if (await storageHealthService.ensureIndexedDBUsable()) {
        const entities = await retrieveRowRepository.getEntitiesByKeys(keys);
        return entities.map((entity, index) => {
          if (!entity) return undefined;
          const renderRow = retrieveRowRepository.applyRenderOverlay(entity);
          if (entity.row) {
            this.setRowMemory(keys[index], entity.row, entity.renderMeta);
          }
          return renderRow ? { row: renderRow, renderMeta: entity.renderMeta } : undefined;
        });
      }
    } catch (error) {
      storageHealthService.resetIndexedDBUsable();
      storageHealthService.notifyIndexedDBFallback();
      console.warn('[retrieve-row-cache] get render entries failed', error);
    }

    return keys.map((key) => {
      const row = this.volatileRows.get(key) || this.rowMemory.get(key)?.value;
      if (!row) return undefined;
      const renderMeta = this.rowMemory.get(key)?.renderMeta || createRetrieveRowRenderMeta(row);
      return { row, renderMeta };
    });
  }

  async getRenderMetas(keys: string[]) {
    if (!keys.length) return [];
    try {
      if (await storageHealthService.ensureIndexedDBUsable()) {
        return retrieveRowRepository.getRenderMetasByKeys(keys);
      }
    } catch (error) {
      storageHealthService.resetIndexedDBUsable();
      storageHealthService.notifyIndexedDBFallback();
      console.warn('[retrieve-row-cache] get render metas failed', error);
    }

    return keys.map(key => {
      const memoryEntry = this.rowMemory.get(key);
      const row = this.volatileRows.get(key) || memoryEntry?.value;
      return memoryEntry?.renderMeta || (row ? createRetrieveRowRenderMeta(row) : undefined);
    });
  }

  async getRows(keys: string[]) {
    const missingKeySet = new Set<string>();
    const output = keys.map((key) => {
      const value = this.volatileRows.get(key) || this.touchRow(key);
      if (!value) missingKeySet.add(key);
      return value;
    });

    if (missingKeySet.size && await storageHealthService.ensureIndexedDBUsable()) {
      const missingKeys = Array.from(missingKeySet);
      try {
        const dbRows = await retrieveRowRepository.getRowsByKeys(missingKeys);
        const rowMap = new Map<string, Record<string, any>>();
        missingKeys.forEach((key, index) => {
          const row = dbRows[index];
          if (row) {
            rowMap.set(key, row);
            this.setRowMemory(key, row);
          }
        });
        output.forEach((row, index) => {
          if (!row) {
            output[index] = rowMap.get(keys[index]);
          }
        });
      } catch (error) {
        storageHealthService.resetIndexedDBUsable();
        storageHealthService.notifyIndexedDBFallback();
        console.warn('[retrieve-row-cache] get rows failed', error);
      }
    }

    return output.filter(Boolean);
  }

  async getProjections(keys: string[]) {
    const missingKeySet = new Set<string>();
    const output = keys.map((key) => {
      const value = this.volatileProjections.get(key) || this.touchProjection(key);
      if (!value) missingKeySet.add(key);
      return value;
    });

    if (missingKeySet.size && await storageHealthService.ensureIndexedDBUsable()) {
      const missingKeys = Array.from(missingKeySet);
      try {
        const dbRows = await retrieveRowRepository.getProjectionsByKeys(missingKeys);
        const projectionMap = new Map<string, RetrieveRowProjection>();
        missingKeys.forEach((key, index) => {
          const projection = dbRows[index];
          if (projection) {
            projectionMap.set(key, projection);
            this.setProjectionMemory(key, projection);
          }
        });
        output.forEach((projection, index) => {
          if (!projection) {
            output[index] = projectionMap.get(keys[index]);
          }
        });
      } catch (error) {
        storageHealthService.resetIndexedDBUsable();
        storageHealthService.notifyIndexedDBFallback();
        console.warn('[retrieve-row-cache] get projections failed', error);
      }
    }

    return output.filter(Boolean);
  }

  async getRowsByQuery(queryKey: string, offset = 0, limit?: number) {
    if (!await storageHealthService.ensureIndexedDBUsable()) {
      return this.getRows(this.createMemoryKeysByQuery(queryKey, offset, limit));
    }
    try {
      const entities = await retrieveRowRepository.getEntitiesByQuery(queryKey, offset, limit);
      entities.forEach((entity) => {
        if (entity?.row) this.setRowMemory(entity.key, entity.row);
      });
      return entities.map(entity => entity?.row).filter(Boolean);
    } catch (error) {
      storageHealthService.resetIndexedDBUsable();
      storageHealthService.notifyIndexedDBFallback();
      console.warn('[retrieve-row-cache] get rows by query failed', error);
      return this.getRows(this.createMemoryKeysByQuery(queryKey, offset, limit));
    }
  }

  async getProjectionsByQuery(queryKey: string, offset = 0, limit?: number) {
    if (!await storageHealthService.ensureIndexedDBUsable()) {
      return this.getProjections(this.createMemoryKeysByQuery(queryKey, offset, limit));
    }
    try {
      const entities = await retrieveRowRepository.getEntitiesByQuery(queryKey, offset, limit);
      entities.forEach((entity) => {
        if (entity?.projection) this.setProjectionMemory(entity.key, entity.projection);
      });
      return entities.map(entity => entity?.projection).filter(Boolean);
    } catch (error) {
      storageHealthService.resetIndexedDBUsable();
      storageHealthService.notifyIndexedDBFallback();
      console.warn('[retrieve-row-cache] get projections by query failed', error);
      return this.getProjections(this.createMemoryKeysByQuery(queryKey, offset, limit));
    }
  }

  async getAllRowsByQuery(queryKey: string) {
    return this.getRowsByQuery(queryKey);
  }

  clearMemory() {
    this.rowMemory.clear();
    this.projectionMemory.clear();
    this.volatileRows.clear();
    this.volatileProjections.clear();
    this.rowMemoryBytes = 0;
    this.projectionMemoryBytes = 0;
  }

  async gc(options: { excludeQueryKeys?: string[] } = {}) {
    return retrieveRowRepository.gc(Date.now(), options);
  }

  releaseQuery(queryKey: string) {
    this.deleteByPrefix(this.rowMemory, queryKey, 'row');
    this.deleteByPrefix(this.projectionMemory, queryKey, 'projection');
    this.deleteVolatileByPrefix(this.volatileRows, queryKey);
    this.deleteVolatileByPrefix(this.volatileProjections, queryKey);
  }

  async clearQuery(queryKey: string) {
    if (!queryKey) return;
    this.releaseQuery(queryKey);
    await retrieveRowRepository.clearQuery(queryKey);
  }

  private createRowKeys(queryKey: string, length: number, startSeq = 0) {
    return Array.from({ length }, (_, index) => `${queryKey}:${startSeq + index}`);
  }

  private createMemoryKeysByQuery(queryKey: string, offset = 0, limit?: number) {
    const prefix = `${queryKey}:`;
    return Array.from(new Set([...this.volatileRows.keys(), ...this.rowMemory.keys()]))
      .filter(key => key.startsWith(prefix))
      .sort((a, b) => Number(a.slice(prefix.length)) - Number(b.slice(prefix.length)))
      .slice(offset, typeof limit === 'number' ? offset + limit : undefined);
  }

  private rememberRows(keys: string[], rows: Record<string, any>[], fieldNames: string[] = [], forceVolatile = false, renderMetas?: RetrieveRowRenderMeta[]) {
    keys.forEach((key, index) => {
      const [queryKey, seqText] = this.resolveKey(key);
      const seq = Number(seqText);
      const storageValue = !Number.isNaN(seq)
        ? retrieveRowProjectionService.createStorageValue(rows[index], queryKey, seq, fieldNames)
        : null;
      if (forceVolatile) {
        this.volatileRows.set(key, rows[index]);
        if (storageValue?.projection) this.volatileProjections.set(key, storageValue.projection);
        return;
      }
      this.setRowMemory(key, rows[index], renderMetas?.[index]);
      if (storageValue?.projection) {
        this.setProjectionMemory(key, storageValue.projection);
      }
    });
  }

  private resolveKey(key: string) {
    const index = key.lastIndexOf(':');
    if (index <= 0) return [key, '0'];
    return [key.slice(0, index), key.slice(index + 1)];
  }

  private touchRow(key: string) {
    const entry = this.rowMemory.get(key);
    if (!entry) return undefined;
    this.rowMemory.delete(key);
    this.rowMemory.set(key, entry);
    return entry.value;
  }

  private touchProjection(key: string) {
    const entry = this.projectionMemory.get(key);
    if (!entry) return undefined;
    this.projectionMemory.delete(key);
    this.projectionMemory.set(key, entry);
    return entry.value;
  }

  private setRowMemory(key: string, row: Record<string, any>, renderMeta?: RetrieveRowRenderMeta) {
    const bytes = estimateValueBytes(row);
    if (bytes > this.maxRowMemoryBytes / 2) return;
    const old = this.rowMemory.get(key);
    if (old) this.rowMemoryBytes -= old.bytes;
    this.rowMemory.set(key, { value: row, bytes, renderMeta });
    this.rowMemoryBytes += bytes;
    this.pruneMemory(this.rowMemory, 'row');
  }

  private setProjectionMemory(key: string, projection: RetrieveRowProjection) {
    const bytes = estimateValueBytes(projection);
    if (bytes > this.maxProjectionMemoryBytes / 2) return;
    const old = this.projectionMemory.get(key);
    if (old) this.projectionMemoryBytes -= old.bytes;
    this.projectionMemory.set(key, { value: projection, bytes });
    this.projectionMemoryBytes += bytes;
    this.pruneMemory(this.projectionMemory, 'projection');
  }

  private pruneMemory(memory: Map<string, MemoryEntry>, type: 'row' | 'projection') {
    const maxBytes = type === 'row' ? this.maxRowMemoryBytes : this.maxProjectionMemoryBytes;
    while ((type === 'row' ? this.rowMemoryBytes : this.projectionMemoryBytes) > maxBytes && memory.size) {
      const key = memory.keys().next().value;
      const entry = memory.get(key);
      memory.delete(key);
      if (type === 'row') this.rowMemoryBytes -= entry?.bytes ?? 0;
      else this.projectionMemoryBytes -= entry?.bytes ?? 0;
    }
  }

  private deleteByPrefix(memory: Map<string, MemoryEntry>, queryKey: string, type: 'row' | 'projection') {
    Array.from(memory.keys()).forEach((key) => {
      if (!key.startsWith(`${queryKey}:`)) return;
      const entry = memory.get(key);
      memory.delete(key);
      if (type === 'row') this.rowMemoryBytes -= entry?.bytes ?? 0;
      else this.projectionMemoryBytes -= entry?.bytes ?? 0;
    });
  }

  private deleteVolatileByPrefix(memory: Map<string, any>, queryKey: string) {
    Array.from(memory.keys()).forEach((key) => {
      if (key.startsWith(`${queryKey}:`)) {
        memory.delete(key);
      }
    });
  }
}

export const retrieveRowCacheService = new RetrieveRowCacheService();
