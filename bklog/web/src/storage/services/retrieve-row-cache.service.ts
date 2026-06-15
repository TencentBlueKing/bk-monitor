/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 */
import { retrieveRowRepository } from '../repositories/retrieve-row.repository';
import { estimateValueBytes, type RetrieveRowProjection } from './retrieve-row-projection.service';

interface MemoryEntry<T = any> {
  value: T;
  bytes: number;
}

interface WriteOptions {
  fieldNames?: string[];
}

export class RetrieveRowCacheService {
  private rowMemory = new Map<string, MemoryEntry<Record<string, any>>>();
  private projectionMemory = new Map<string, MemoryEntry<RetrieveRowProjection>>();
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
    return `retrieve:${Date.now()}:${Math.abs(hash)}`;
  }

  async replaceRows(queryKey: string, rows: Record<string, any>[], options: WriteOptions = {}) {
    this.clearMemory();
    const keys = await retrieveRowRepository.replaceRows(queryKey, rows, 0, options);
    this.rememberRows(keys, rows);
    retrieveRowRepository.gc();
    return keys;
  }

  async appendRows(queryKey: string, rows: Record<string, any>[], startSeq: number, options: WriteOptions = {}) {
    const keys = await retrieveRowRepository.appendRows(queryKey, rows, startSeq, options);
    this.rememberRows(keys, rows);
    return keys;
  }

  getMemoryRows(keys: string[]) {
    return keys.map(key => this.rowMemory.get(key)?.value).filter(Boolean);
  }

  async getRows(keys: string[]) {
    const missingKeySet = new Set<string>();
    const output = keys.map((key) => {
      const value = this.touchRow(key);
      if (!value) missingKeySet.add(key);
      return value;
    });

    if (missingKeySet.size) {
      const missingKeys = Array.from(missingKeySet);
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
    }

    return output.filter(Boolean);
  }

  async getProjections(keys: string[]) {
    const missingKeySet = new Set<string>();
    const output = keys.map((key) => {
      const value = this.touchProjection(key);
      if (!value) missingKeySet.add(key);
      return value;
    });

    if (missingKeySet.size) {
      const missingKeys = Array.from(missingKeySet);
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
    }

    return output.filter(Boolean);
  }

  async getRowsByQuery(queryKey: string, offset = 0, limit?: number) {
    const rows = await retrieveRowRepository.getRowsByQuery(queryKey, offset, limit);
    rows.forEach((row, index) => {
      this.setRowMemory(`${queryKey}:${offset + index}`, row);
    });
    return rows;
  }

  async getProjectionsByQuery(queryKey: string, offset = 0, limit?: number) {
    const projections = await retrieveRowRepository.getProjectionsByQuery(queryKey, offset, limit);
    projections.forEach((projection, index) => {
      this.setProjectionMemory(`${queryKey}:${offset + index}`, projection);
    });
    return projections;
  }

  async getAllRowsByQuery(queryKey: string) {
    return this.getRowsByQuery(queryKey);
  }

  clearMemory() {
    this.rowMemory.clear();
    this.projectionMemory.clear();
    this.rowMemoryBytes = 0;
    this.projectionMemoryBytes = 0;
  }

  releaseQuery(queryKey: string) {
    this.deleteByPrefix(this.rowMemory, queryKey, 'row');
    this.deleteByPrefix(this.projectionMemory, queryKey, 'projection');
  }

  private rememberRows(keys: string[], rows: Record<string, any>[]) {
    keys.forEach((key, index) => {
      this.setRowMemory(key, rows[index]);
    });
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

  private setRowMemory(key: string, row: Record<string, any>) {
    const bytes = estimateValueBytes(row);
    if (bytes > this.maxRowMemoryBytes / 2) return;
    const old = this.rowMemory.get(key);
    if (old) this.rowMemoryBytes -= old.bytes;
    this.rowMemory.set(key, { value: row, bytes });
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
}

export const retrieveRowCacheService = new RetrieveRowCacheService();
