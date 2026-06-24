/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 */
import Dexie, { type Table } from 'dexie';

export interface RetrieveRowEntity {
  key: string;
  queryKey: string;
  seq: number;
  row: Record<string, any>;
  renderOverlay?: any;
  projection?: any;
  renderMeta?: any;
  bytes?: number;
  createdAt: number;
  expireAt: number;
}

export interface KeyValueEntity {
  key: string;
  value: any;
  updatedAt: number;
  expireAt: number;
}

export interface ApiCacheEntity {
  key: string;
  data: any;
  meta: Record<string, any>;
  updatedAt: number;
  expireAt: number;
}

export interface PerformanceRecordEntity {
  id?: number;
  sessionId: string;
  type: string;
  timestamp: number;
  routeFullPath?: string;
  routeName?: string;
  componentPath?: string;
  tabId?: string;
  pageId?: string;
  data: any;
}

class BkLogStorageDB extends Dexie {
  retrieveRows!: Table<RetrieveRowEntity, string>;
  keyValues!: Table<KeyValueEntity, string>;
  apiCaches!: Table<ApiCacheEntity, string>;
  performanceRecords!: Table<PerformanceRecordEntity, number>;

  constructor() {
    super('bklog-web-storage');

    // IndexedDB is first introduced in this version. Keep only the final schema;
    // there is no released legacy IndexedDB cache to migrate.
    this.version(1).stores({
      retrieveRows: 'key, queryKey, [queryKey+seq], seq, expireAt',
      keyValues: 'key, expireAt, updatedAt',
      apiCaches: 'key, expireAt, updatedAt',
      performanceRecords: '++id, sessionId, type, timestamp, routeFullPath',
    });
  }
}

export const db = new BkLogStorageDB();
export default db;
