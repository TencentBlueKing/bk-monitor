/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 */
import { storeCacheService } from './store-cache.service';
import { estimateValueBytes } from './retrieve-row-projection.service';

interface ListManifest {
  scope: string;
  total: number;
  chunkSize: number;
  chunkCount: number;
  updatedAt: number;
  bytes: number;
}

interface MemoryListEntry {
  manifest: ListManifest;
  chunks: Map<number, any[]>;
  bytes: number;
}

const DEFAULT_CHUNK_SIZE = 50;
const DEFAULT_MAX_MEMORY_BYTES = 16 * 1024 * 1024;
const CACHE_NAME = 'module-large-list';

const nextIdle = () => new Promise(resolve => setTimeout(resolve, 0));

const getChunkScope = (scope: string, index: number) => `${scope}:chunk:${index}`;
const getManifestScope = (scope: string) => `${scope}:manifest`;

export class ModuleLargeDataCacheService {
  private memory = new Map<string, MemoryListEntry>();
  private maxMemoryBytes = DEFAULT_MAX_MEMORY_BYTES;
  private memoryBytes = 0;

  createScope(prefix: string, params: Record<string, any> = {}) {
    const seed = JSON.stringify(params ?? {});
    let hash = 0;
    for (let i = 0; i < seed.length; i++) {
      hash = (hash * 31 + seed.charCodeAt(i)) | 0;
    }
    return `${prefix}:${Date.now()}:${Math.abs(hash)}`;
  }

  async replaceList(scope: string, list: any[] = [], chunkSize = DEFAULT_CHUNK_SIZE) {
    await this.clear(scope);
    const chunks = new Map<number, any[]>();
    let bytes = 0;
    const chunkCount = Math.ceil(list.length / chunkSize);

    for (let index = 0; index < chunkCount; index++) {
      const chunk = list.slice(index * chunkSize, (index + 1) * chunkSize);
      bytes += estimateValueBytes(chunk);
      await storeCacheService.setApiCache(CACHE_NAME, getChunkScope(scope, index), chunk, {
        scope,
        index,
        chunkSize,
      });
      this.rememberChunk(chunks, index, chunk);
      await nextIdle();
    }

    const manifest: ListManifest = {
      scope,
      total: list.length,
      chunkSize,
      chunkCount,
      updatedAt: Date.now(),
      bytes,
    };
    await storeCacheService.setApiCache(CACHE_NAME, getManifestScope(scope), manifest, { scope });
    this.setMemory(scope, { manifest, chunks, bytes });
    return manifest;
  }

  async getManifest(scope: string) {
    const memory = this.memory.get(scope);
    if (memory) return memory.manifest;
    return storeCacheService.getApiCache<ListManifest>(CACHE_NAME, getManifestScope(scope));
  }

  async getSlice<T = any>(scope: string, offset = 0, limit = DEFAULT_CHUNK_SIZE): Promise<T[]> {
    const manifest = await this.getManifest(scope);
    if (!manifest || limit <= 0) return [];

    const start = Math.max(0, offset);
    const end = Math.min(manifest.total, start + limit);
    if (start >= end) return [];

    const startChunk = Math.floor(start / manifest.chunkSize);
    const endChunk = Math.floor((end - 1) / manifest.chunkSize);
    const output: T[] = [];

    for (let index = startChunk; index <= endChunk; index++) {
      const chunk = await this.getChunk<T>(scope, index);
      const chunkStart = index * manifest.chunkSize;
      const from = Math.max(0, start - chunkStart);
      const to = Math.min(chunk.length, end - chunkStart);
      output.push(...chunk.slice(from, to));
    }

    return output;
  }

  async getAll<T = any>(scope: string) {
    const manifest = await this.getManifest(scope);
    if (!manifest) return [];
    return this.getSlice<T>(scope, 0, manifest.total);
  }

  async clear(scope: string) {
    const manifest = await this.getManifest(scope);
    if (manifest) {
      const removals: Promise<any>[] = [];
      for (let index = 0; index < manifest.chunkCount; index++) {
        removals.push(storeCacheService.removeApiCache(CACHE_NAME, getChunkScope(scope, index)));
      }
      removals.push(storeCacheService.removeApiCache(CACHE_NAME, getManifestScope(scope)));
      await Promise.all(removals);
    }
    this.deleteMemory(scope);
  }

  clearMemory(scope?: string) {
    if (scope) {
      this.deleteMemory(scope);
      return;
    }
    this.memory.clear();
    this.memoryBytes = 0;
  }

  private async getChunk<T = any>(scope: string, index: number): Promise<T[]> {
    const memory = this.memory.get(scope)?.chunks.get(index);
    if (memory) return memory as T[];

    const chunk = await storeCacheService.getApiCache<T[]>(CACHE_NAME, getChunkScope(scope, index));
    if (!chunk) return [];

    const entry = this.memory.get(scope);
    if (entry) {
      this.rememberChunk(entry.chunks, index, chunk);
      entry.bytes += estimateValueBytes(chunk);
      this.memoryBytes += estimateValueBytes(chunk);
      this.pruneMemory();
    }
    return chunk;
  }

  private rememberChunk(chunks: Map<number, any[]>, index: number, chunk: any[]) {
    const bytes = estimateValueBytes(chunk);
    if (bytes > this.maxMemoryBytes / 2) return;
    chunks.set(index, chunk);
  }

  private setMemory(scope: string, entry: MemoryListEntry) {
    if (entry.bytes > this.maxMemoryBytes / 2) {
      entry.chunks.clear();
      entry.bytes = estimateValueBytes(entry.manifest);
    }
    this.deleteMemory(scope);
    this.memory.set(scope, entry);
    this.memoryBytes += entry.bytes;
    this.pruneMemory();
  }

  private deleteMemory(scope: string) {
    const entry = this.memory.get(scope);
    if (!entry) return;
    this.memory.delete(scope);
    this.memoryBytes -= entry.bytes;
  }

  private pruneMemory() {
    while (this.memoryBytes > this.maxMemoryBytes && this.memory.size) {
      const key = this.memory.keys().next().value;
      this.deleteMemory(key);
    }
  }
}

export const moduleLargeDataCacheService = new ModuleLargeDataCacheService();
