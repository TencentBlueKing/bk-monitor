/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 */
import db from '../core/db';

const SUPPORT_NOTICE_KEY = '__bklog_storage_support_notice__';
const ACTIVE_QUERY_STORAGE_KEY = '__bklog_active_retrieve_query_keys__';
const TAB_ID_STORAGE_KEY = '__bklog_storage_tab_id__';
const ACTIVE_QUERY_TTL = 10 * 60 * 1000;

const getMessageInstance = () => {
  const mainComponent = (window as any).mainComponent;
  return mainComponent?.$bkMessage || mainComponent?.$bkNotify || null;
};

const showWarning = (message: string) => {
  const messageInstance = getMessageInstance();
  if (typeof messageInstance === 'function') {
    messageInstance({
      theme: 'warning',
      message,
    });
    return;
  }

  console.warn(message);
};

class StorageHealthService {
  private indexedDBUsable: boolean | null = null;
  private tabId = this.createTabId();
  private workerFallbackNotified = false;
  private indexedDBFallbackNotified = false;
  private compatibilityNotified = false;

  isIndexedDBSupported() {
    return typeof window !== 'undefined' && typeof window.indexedDB !== 'undefined';
  }

  isWorkerSupported() {
    return typeof Worker !== 'undefined' && typeof URL !== 'undefined';
  }

  async ensureIndexedDBUsable() {
    if (this.indexedDBUsable !== null) return this.indexedDBUsable;

    if (!this.isIndexedDBSupported()) {
      this.indexedDBUsable = false;
      return false;
    }

    try {
      await db.open();
      this.indexedDBUsable = true;
      return true;
    } catch (error) {
      console.warn('[bklog-storage] IndexedDB open failed', error);
      this.indexedDBUsable = false;
      return false;
    }
  }

  resetIndexedDBUsable() {
    this.indexedDBUsable = null;
  }

  notifyCompatibilityIssue(reason?: string) {
    if (this.compatibilityNotified || this.safeSessionGet(SUPPORT_NOTICE_KEY) === '1') return;
    this.compatibilityNotified = true;
    this.safeSessionSet(SUPPORT_NOTICE_KEY, '1');
    showWarning(
      reason
        || '当前浏览器不支持或限制了 IndexedDB，本次检索将使用内存降级模式；大日志结果可能出现加载变慢或无法完整展示，建议使用最新版 Chrome / Edge。',
    );
  }

  notifyWorkerFallback(reason?: string) {
    if (this.workerFallbackNotified) return;
    this.workerFallbackNotified = true;
    showWarning(
      reason
        || 'WebWorker 解析检索结果失败，已自动降级为主线程解析；功能不受影响，但大数据检索期间页面可能短暂卡顿。',
    );
  }

  notifyIndexedDBFallback(reason?: string) {
    if (this.indexedDBFallbackNotified) return;
    this.indexedDBFallbackNotified = true;
    showWarning(
      reason
        || 'IndexedDB 写入检索结果失败，已自动降级为当前页面内存缓存；功能可继续使用，但刷新或切换页面后结果缓存不会保留。',
    );
  }

  markActiveQuery(queryKey: string) {
    if (!queryKey) return;
    const records = this.getActiveQueryRecords();
    records[this.tabId] = { queryKey, updatedAt: Date.now() };
    this.setActiveQueryRecords(records);
  }

  clearActiveQuery(queryKey?: string) {
    const records = this.getActiveQueryRecords();
    if (!records[this.tabId]) return;
    if (!queryKey || records[this.tabId].queryKey === queryKey) {
      delete records[this.tabId];
      this.setActiveQueryRecords(records);
    }
  }

  getActiveQueryKeys() {
    const now = Date.now();
    const records = this.getActiveQueryRecords();
    let changed = false;
    const activeKeys = Object.keys(records).reduce((out, tabId) => {
      const record = records[tabId];
      if (!record?.queryKey || now - record.updatedAt > ACTIVE_QUERY_TTL) {
        delete records[tabId];
        changed = true;
        return out;
      }
      out.push(record.queryKey);
      return out;
    }, [] as string[]);
    if (changed) this.setActiveQueryRecords(records);
    return activeKeys;
  }

  private createTabId() {
    const existing = this.safeSessionGet(TAB_ID_STORAGE_KEY);
    if (existing) return existing;
    const next = typeof crypto !== 'undefined' && crypto.randomUUID
      ? crypto.randomUUID()
      : `${Date.now()}:${Math.random().toString(16).slice(2)}`;
    this.safeSessionSet(TAB_ID_STORAGE_KEY, next);
    return next;
  }

  private getActiveQueryRecords(): Record<string, { queryKey: string; updatedAt: number }> {
    try {
      return JSON.parse(this.safeLocalGet(ACTIVE_QUERY_STORAGE_KEY) || '{}');
    } catch (error) {
      console.warn('[bklog-storage] parse active query records failed', error);
      return {};
    }
  }

  private setActiveQueryRecords(records: Record<string, { queryKey: string; updatedAt: number }>) {
    this.safeLocalSet(ACTIVE_QUERY_STORAGE_KEY, JSON.stringify(records));
  }

  private safeSessionGet(key: string) {
    try {
      return sessionStorage.getItem(key);
    } catch (_) {
      return null;
    }
  }

  private safeSessionSet(key: string, value: string) {
    try {
      sessionStorage.setItem(key, value);
    } catch (_) {}
  }

  private safeLocalGet(key: string) {
    try {
      return localStorage.getItem(key);
    } catch (_) {
      return null;
    }
  }

  private safeLocalSet(key: string, value: string) {
    try {
      localStorage.setItem(key, value);
    } catch (_) {}
  }
}

export const storageHealthService = new StorageHealthService();
