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

    this.version(1).stores({
      retrieveRows: 'key, queryKey, seq, expireAt',
    });

    this.version(2).stores({
      retrieveRows: 'key, queryKey, seq, expireAt',
      keyValues: 'key, expireAt, updatedAt',
      apiCaches: 'key, expireAt, updatedAt',
    });

    this.version(3).stores({
      retrieveRows: 'key, queryKey, [queryKey+seq], seq, expireAt',
      keyValues: 'key, expireAt, updatedAt',
      apiCaches: 'key, expireAt, updatedAt',
    });

    this.version(4).stores({
      retrieveRows: 'key, queryKey, [queryKey+seq], seq, expireAt',
      keyValues: 'key, expireAt, updatedAt',
      apiCaches: 'key, expireAt, updatedAt',
      performanceRecords: '++id, sessionId, type, timestamp, routeFullPath',
    });
  }
}

export const db = new BkLogStorageDB();
export default db;
