/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 */
import db from '../core/db';
import { PAGE_INSTANCE_ID } from '../utils/page-instance';

const SUPPORT_NOTICE_KEY = '__bklog_storage_support_notice__';
const ACTIVE_QUERY_TTL = 5 * 60 * 1000;
const ACTIVE_QUERY_HEARTBEAT = 60 * 1000;

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
  private readonly pageInstanceId = PAGE_INSTANCE_ID;
  private workerFallbackNotified = false;
  private indexedDBFallbackNotified = false;
  private compatibilityNotified = false;
  private activeQueryKey = '';
  private heartbeatTimer: ReturnType<typeof setInterval> | null = null;
  private activeMutation = Promise.resolve();

  constructor() {
    if (typeof window !== 'undefined') {
      window.addEventListener('pagehide', () => {
        this.stopHeartbeat();
        void this.enqueueActiveMutation(() => this.deleteActiveOwner());
      });
      window.addEventListener('pageshow', (event) => {
        if ((event as PageTransitionEvent).persisted && this.activeQueryKey) {
          this.startHeartbeat();
          void this.enqueueActiveMutation(() => this.persistActiveQuery(this.activeQueryKey));
        }
      });
    }
  }

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
    if (!queryKey) return Promise.resolve();
    this.activeQueryKey = queryKey;
    this.startHeartbeat();
    return this.enqueueActiveMutation(() => this.persistActiveQuery(queryKey));
  }

  clearActiveQuery(queryKey?: string) {
    if (queryKey && this.activeQueryKey && this.activeQueryKey !== queryKey) return Promise.resolve();
    this.activeQueryKey = '';
    this.stopHeartbeat();
    return this.enqueueActiveMutation(() => this.deleteActiveOwner());
  }

  async getActiveQueryKeys() {
    await this.activeMutation;
    if (!(await this.ensureIndexedDBUsable())) {
      return this.activeQueryKey ? [this.activeQueryKey] : [];
    }
    const now = Date.now();
    try {
      await db.activeRetrieveQueries
        .where('expireAt')
        .belowOrEqual(now)
        .delete();
      const records = await db.activeRetrieveQueries
        .where('expireAt')
        .above(now)
        .toArray();
      return Array.from(new Set(records.map(record => record.queryKey).filter(Boolean)));
    } catch (error) {
      console.warn('[bklog-storage] get active query keys failed', error);
      return this.activeQueryKey ? [this.activeQueryKey] : [];
    }
  }

  getPageInstanceId() {
    return this.pageInstanceId;
  }

  private async deleteActiveOwner() {
    try {
      if (await this.ensureIndexedDBUsable()) {
        await db.activeRetrieveQueries.delete(this.pageInstanceId);
      }
    } catch (error) {
      console.warn('[bklog-storage] clear active query failed', error);
    }
  }

  private async persistActiveQuery(queryKey: string) {
    try {
      if (!(await this.ensureIndexedDBUsable()) || queryKey !== this.activeQueryKey) return;
      const now = Date.now();
      await db.activeRetrieveQueries.put({
        ownerId: this.pageInstanceId,
        queryKey,
        updatedAt: now,
        expireAt: now + ACTIVE_QUERY_TTL,
      });
    } catch (error) {
      console.warn('[bklog-storage] mark active query failed', error);
    }
  }

  private startHeartbeat() {
    if (this.heartbeatTimer) return;
    this.heartbeatTimer = setInterval(() => {
      if (this.activeQueryKey) {
        const queryKey = this.activeQueryKey;
        void this.enqueueActiveMutation(() => this.persistActiveQuery(queryKey));
      }
    }, ACTIVE_QUERY_HEARTBEAT);
  }

  private stopHeartbeat() {
    if (!this.heartbeatTimer) return;
    clearInterval(this.heartbeatTimer);
    this.heartbeatTimer = null;
  }

  private enqueueActiveMutation(operation: () => Promise<void>) {
    const task = this.activeMutation.then(operation, operation);
    this.activeMutation = task.catch((error) => {
      console.warn('[bklog-storage] active query mutation failed', error);
    });
    return task;
  }

  private safeSessionGet(key: string) {
    try {
      return sessionStorage.getItem(key);
    } catch {
      return null;
    }
  }

  private safeSessionSet(key: string, value: string) {
    try {
      sessionStorage.setItem(key, value);
    } catch {
      // Storage access can be denied in private or hardened browser contexts.
    }
  }
}

export const storageHealthService = new StorageHealthService();
