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
  highlightField?: string;
  copyExcludedFields?: string[];
  renderOverlay?: any;
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

export interface RetrieveFieldMetaEntity {
  key: string;
  scope: string;
  rawPayload: any;
  normalizedPayload: any;
  rawFields: any[];
  rawFieldList: any[];
  aliasFieldList: any[];
  fieldTree: any[];
  fieldNameIndex: Record<string, any>;
  queryAliasIndex: Record<string, any>;
  widthHints?: Record<string, any>;
  createdAt: number;
  updatedAt: number;
  expireAt: number;
}

export interface RetrieveFieldWidthEntity {
  key: string;
  scope: string;
  fieldName: string;
  serverMaxLength?: number;
  computedWidth?: number;
  minWidth?: number;
  userWidth?: number;
  source?: string;
  updatedAt: number;
  expireAt: number;
}

export interface RetrieveFieldAliasConfigEntity {
  key: string;
  scope: string;
  rawFieldList: any[];
  aliasFieldList: any[];
  fieldNameIndex: Record<string, any>;
  queryAliasIndex: Record<string, any>;
  repeatAliasGroups: Record<
    string,
    {
      query_alias: string;
      source_field_names: string[];
      virtual_field_name?: string;
    }
  >;
  createdAt: number;
  updatedAt: number;
  expireAt: number;
}

class BkLogStorageDB extends Dexie {
  retrieveRows!: Table<RetrieveRowEntity, string>;
  keyValues!: Table<KeyValueEntity, string>;
  apiCaches!: Table<ApiCacheEntity, string>;
  performanceRecords!: Table<PerformanceRecordEntity, number>;
  retrieveFieldMetas!: Table<RetrieveFieldMetaEntity, string>;
  retrieveFieldWidths!: Table<RetrieveFieldWidthEntity, string>;
  retrieveFieldAliasConfigs!: Table<RetrieveFieldAliasConfigEntity, string>;

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

    this.version(2).stores({
      retrieveRows: 'key, queryKey, [queryKey+seq], seq, expireAt',
      keyValues: 'key, expireAt, updatedAt',
      apiCaches: 'key, expireAt, updatedAt',
      performanceRecords: '++id, sessionId, type, timestamp, routeFullPath',
      retrieveFieldMetas: 'key, scope, updatedAt, expireAt',
      retrieveFieldWidths: 'key, scope, [scope+fieldName], fieldName, updatedAt, expireAt',
    });

    this.version(3).stores({
      retrieveRows: 'key, queryKey, [queryKey+seq], seq, expireAt',
      keyValues: 'key, expireAt, updatedAt',
      apiCaches: 'key, expireAt, updatedAt',
      performanceRecords: '++id, sessionId, type, timestamp, routeFullPath',
      retrieveFieldMetas: 'key, scope, updatedAt, expireAt',
      retrieveFieldWidths: 'key, scope, [scope+fieldName], fieldName, updatedAt, expireAt',
      retrieveFieldAliasConfigs: 'key, scope, updatedAt, expireAt',
    });
  }
}

export const db = new BkLogStorageDB();
export default db;
