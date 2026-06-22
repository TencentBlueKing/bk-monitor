/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 */
import { storageHealthService } from './storage-health.service';
import { workerManagerService } from './worker-manager.service';

interface WorkerIngestOptions {
  fieldNames?: string[];
  queryKey: string;
  startSeq?: number;
  timeout?: number;
  writeMode?: 'append' | 'replace';
}

interface WorkerIngestResult {
  code?: string;
  data: Record<string, any>;
  length: number;
  message?: string;
  permission?: any;
  result: boolean;
  rowKeys: string[];
  size: number;
}

interface WorkerConnectionTestResult {
  baseURI: string;
  indexedDBSupported: boolean;
  ok: boolean;
  staticUrl: string;
  userAgent: string;
  workerSupported: boolean;
  workerUrl: string;
  error?: string;
  event?: Record<string, any>;
  message?: any;
}

const DEFAULT_TIMEOUT = 120000;
const DEFAULT_DIAGNOSTIC_TIMEOUT = 8000;
const WORK_ID = 'retrieve-search-ingest';

class RetrieveSearchWorkerIngestService {
  private workerSupported = typeof Worker !== 'undefined' && typeof URL !== 'undefined';

  constructor() {
    workerManagerService.register({
      description: '检索 /search API 响应解析并写入 IndexedDB 的 WebWorker',
      getRuntimeStatus: () => this.getRuntimeStatus(),
      id: WORK_ID,
      kind: 'web-worker',
      name: 'Retrieve Search Ingest Worker',
      ping: () => this.testConnection(),
    });
  }

  getRuntimeStatus() {
    return {
      baseURI: typeof document !== 'undefined' ? document.baseURI : '',
      indexedDBSupported: typeof window !== 'undefined' && typeof window.indexedDB !== 'undefined',
      staticUrl: typeof window !== 'undefined' ? String((window as any).BK_STATIC_URL || '') : '',
      userAgent: typeof navigator !== 'undefined' ? navigator.userAgent : '',
      workerSupported: this.workerSupported,
      // `window.workers` 不是浏览器标准 API，Worker 支持情况应检查 `window.Worker`。
      windowWorkerType: typeof window !== 'undefined' ? typeof (window as any).Worker : 'undefined',
      windowWorkersType: typeof window !== 'undefined' ? typeof (window as any).workers : 'undefined',
      workerUrl: this.getWorkerUrl(),
    };
  }

  getWorkerUrl() {
    try {
      return new URL('../workers/retrieve-search-ingest.worker.ts', import.meta.url).toString();
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      return `resolve-worker-url-failed:${message}`;
    }
  }

  async testConnection(timeout = DEFAULT_DIAGNOSTIC_TIMEOUT): Promise<WorkerConnectionTestResult> {
    const status = this.getRuntimeStatus();
    workerManagerService.update(WORK_ID, { state: 'loading', url: status.workerUrl });
    if (!this.workerSupported) {
      workerManagerService.update(WORK_ID, { lastError: 'WebWorker is not supported', state: 'unsupported' });
      return {
        ...status,
        ok: false,
        error: 'WebWorker is not supported. Please check window.Worker instead of window.workers.',
      };
    }

    let worker: Worker | null = null;
    let timer: ReturnType<typeof setTimeout> | null = null;
    const id = `worker-diagnostic:${Date.now()}:${Math.random().toString(16).slice(2)}`;

    try {
      worker = this.createWorker();
      return await new Promise<WorkerConnectionTestResult>((resolve) => {
        const cleanupWorker = () => {
          if (timer) clearTimeout(timer);
          timer = null;
          if (worker) {
            worker.onmessage = null;
            worker.onerror = null;
            worker.onmessageerror = null;
            worker.terminate();
            worker = null;
          }
        };

        timer = setTimeout(() => {
          cleanupWorker();
          workerManagerService.update(WORK_ID, {
            lastError: `WebWorker diagnostic timeout after ${timeout}ms`,
            state: 'error',
          });
          resolve({
            ...status,
            ok: false,
            error: `WebWorker diagnostic timeout after ${timeout}ms`,
          });
        }, timeout);

        worker!.onmessage = (event: MessageEvent<any>) => {
          const message = event.data;
          if (message?.id !== id) return;
          cleanupWorker();
          workerManagerService.update(WORK_ID, {
            lastError: message.ok ? undefined : message.error,
            lastOkAt: message.ok ? Date.now() : undefined,
            state: message.ok ? 'idle' : 'error',
          });
          resolve({
            ...status,
            ok: !!message.ok,
            message,
          });
        };

        worker!.onmessageerror = (event: MessageEvent<any>) => {
          cleanupWorker();
          workerManagerService.update(WORK_ID, {
            lastError: 'WebWorker messageerror',
            state: 'error',
          });
          resolve({
            ...status,
            ok: false,
            error: 'WebWorker messageerror',
            event: { data: event.data },
          });
        };

        worker!.onerror = (error: ErrorEvent) => {
          cleanupWorker();
          workerManagerService.update(WORK_ID, {
            lastError: error.message || 'WebWorker script load failed',
            state: 'error',
          });
          resolve({
            ...status,
            ok: false,
            error: error.message || 'WebWorker script load failed',
            event: {
              colno: error.colno,
              filename: error.filename,
              lineno: error.lineno,
              message: error.message,
              type: error.type,
            },
          });
        };

        worker!.postMessage({ id, type: 'ping' });
      });
    } catch (error) {
      if (timer) clearTimeout(timer);
      if (worker) {
        worker.onmessage = null;
        worker.onerror = null;
        worker.onmessageerror = null;
        worker.terminate();
      }
      workerManagerService.update(WORK_ID, {
        lastError: error instanceof Error ? error.message : String(error),
        state: 'error',
      });
      return {
        ...status,
        ok: false,
        error: error instanceof Error ? error.message : String(error),
      };
    }
  }

  async ingestBlob(blob: Blob, options: WorkerIngestOptions): Promise<WorkerIngestResult> {
    workerManagerService.incrementMetric(WORK_ID, 'ingestStart');
    workerManagerService.update(WORK_ID, { state: 'running', url: this.getWorkerUrl() });
    if (!this.workerSupported) {
      workerManagerService.incrementMetric(WORK_ID, 'ingestUnsupported');
      workerManagerService.update(WORK_ID, { lastError: 'WebWorker is not supported', state: 'unsupported' });
      storageHealthService.notifyCompatibilityIssue('当前浏览器不支持 WebWorker，本次检索将使用主线程解析；功能不受影响，但大数据检索期间页面可能短暂卡顿。');
      throw new Error('WebWorker is not supported');
    }

    const indexedDBUsable = await storageHealthService.ensureIndexedDBUsable();
    if (!indexedDBUsable) {
      workerManagerService.incrementMetric(WORK_ID, 'ingestIndexedDBUnavailable');
      workerManagerService.update(WORK_ID, { lastError: 'IndexedDB is not usable in WebWorker ingest', state: 'error' });
      storageHealthService.notifyCompatibilityIssue();
      throw new Error('IndexedDB is not usable in WebWorker ingest');
    }

    let worker: Worker | null = null;
    let timer: ReturnType<typeof setTimeout> | null = null;

    try {
      const buffer = await blob.arrayBuffer();
      worker = this.createWorker();
      const id = `search-ingest:${Date.now()}:${Math.random().toString(16).slice(2)}`;

      return await new Promise<WorkerIngestResult>((resolve, reject) => {
        const cleanupWorker = () => {
          if (timer) clearTimeout(timer);
          timer = null;
          if (worker) {
            worker.onmessage = null;
            worker.onerror = null;
            worker.terminate();
            worker = null;
          }
        };

        timer = setTimeout(() => {
          cleanupWorker();
          workerManagerService.incrementMetric(WORK_ID, 'ingestTimeout');
          workerManagerService.update(WORK_ID, { lastError: 'WebWorker search ingest timeout', state: 'error' });
          reject(new Error('WebWorker search ingest timeout'));
        }, options.timeout ?? DEFAULT_TIMEOUT);

        worker!.onmessage = (event: MessageEvent<any>) => {
          const message = event.data;
          if (message?.id !== id) return;
          cleanupWorker();

          if (!message.ok) {
            workerManagerService.incrementMetric(WORK_ID, 'ingestFailed');
            workerManagerService.update(WORK_ID, { lastError: message.error || 'WebWorker search ingest failed', state: 'error' });
            reject(new Error(message.error || 'WebWorker search ingest failed'));
            return;
          }

          workerManagerService.incrementMetric(WORK_ID, 'ingestSuccess');
          workerManagerService.update(WORK_ID, {
            lastError: undefined,
            lastOkAt: Date.now(),
            metrics: {
              lastIngestRows: message.size || 0,
              lastWriteMode: options.writeMode || 'replace',
            },
            state: 'idle',
          });

          resolve({
            code: message.response?.code,
            data: message.response?.data || {},
            length: message.size || 0,
            message: message.response?.message,
            permission: message.response?.permission,
            result: !!message.response?.result,
            rowKeys: message.rowKeys || [],
            size: message.size || 0,
          });
        };

        worker!.onerror = (error) => {
          const detail = error instanceof ErrorEvent
            ? `${error.message || 'WebWorker script load failed'}${error.filename ? ` (${error.filename}:${error.lineno}:${error.colno})` : ''}`
            : String(error);
          cleanupWorker();
          workerManagerService.incrementMetric(WORK_ID, 'ingestFailed');
          workerManagerService.update(WORK_ID, { lastError: detail, state: 'error' });
          reject(new Error(detail));
        };

        worker!.onmessageerror = (error) => {
          const detail = `WebWorker message error: ${String(error?.data || error)}`;
          cleanupWorker();
          workerManagerService.incrementMetric(WORK_ID, 'ingestFailed');
          workerManagerService.update(WORK_ID, { lastError: detail, state: 'error' });
          reject(new Error(detail));
        };

        worker!.postMessage({
          id,
          buffer,
          fieldNames: options.fieldNames || [],
          queryKey: options.queryKey,
          startSeq: options.startSeq || 0,
          type: 'ingest-search-response',
          writeMode: options.writeMode || 'replace',
        }, [buffer]);
      });
    } catch (error) {
      if (timer) clearTimeout(timer);
      if (worker) {
        worker.onmessage = null;
        worker.onerror = null;
        worker.terminate();
      }
      workerManagerService.incrementMetric(WORK_ID, 'ingestFailed');
      workerManagerService.update(WORK_ID, {
        lastError: error instanceof Error ? error.message : String(error),
        state: 'error',
      });
      throw error;
    }
  }

  private createWorker() {
    return new Worker(new URL('../workers/retrieve-search-ingest.worker.ts', import.meta.url));
  }
}

export const retrieveSearchWorkerIngestService = new RetrieveSearchWorkerIngestService();
