/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 */
import { storageHealthService } from './storage-health.service';
import { workerManagerService } from './worker-manager.service';
import {
  categorizeIngestError,
  computeIngestTimeout,
  // logRetrieveSearchIngest,
  type RetrieveSearchIngestErrorCategory,
} from '../utils/retrieve-search-ingest.logger';

export interface SearchStreamRequest {
  baseURL: string;
  body: Record<string, any>;
  fieldNames?: string[];
  headers?: Record<string, string>;
  onProgress?: (progress: SearchStreamProgress) => void;
  queryKey: string;
  searchPath: string;
  startSeq?: number;
  timeout?: number;
  writeMode?: 'append' | 'replace';
}

export interface SearchStreamProgress {
  meta?: Record<string, any>;
  queryKey?: string;
  rowCount?: number;
  rowKeys?: string[];
  stage: string;
}

export interface SearchStreamResult {
  code?: string;
  data: Record<string, any>;
  length: number;
  message?: string;
  permission?: any;
  result: boolean;
  rowKeys: string[];
  size: number;
  source: 'worker';
  timings?: Record<string, number>;
}

interface PendingSearchRequest {
  onProgress?: (progress: SearchStreamProgress) => void;
  reject: (error: Error) => void;
  resolve: (value: SearchStreamResult) => void;
  startedAt: number;
  timer: ReturnType<typeof setTimeout> | null;
}

const DEFAULT_DIAGNOSTIC_TIMEOUT = 8000;
const WORK_ID = 'retrieve-search-ingest';

const buildSearchUrl = (baseURL: string, searchPath: string) => {
  const normalizedBase = baseURL.startsWith('http')
    ? baseURL.replace(/\/$/, '')
    : `${window.location.origin}${baseURL.startsWith('/') ? '' : '/'}${baseURL}`.replace(/\/$/, '');
  const normalizedPath = searchPath.startsWith('/') ? searchPath : `/${searchPath}`;
  const url = new URL(`${normalizedBase}${normalizedPath}`);
  url.searchParams.set('stream', 'true');
  return url.toString();
};

class RetrieveSearchWorkerService {
  private workerSupported = typeof Worker !== 'undefined' && typeof URL !== 'undefined';
  private activeWorker: Worker | null = null;
  private searchQueue: Promise<void> = Promise.resolve();
  private pendingRequests = new Map<string, PendingSearchRequest>();
  private activeRequestId: string | null = null;

  constructor() {
    workerManagerService.register({
      description: '检索 /search NDJSON 流式请求、解析并写入 IndexedDB 的 WebWorker',
      getRuntimeStatus: () => this.getRuntimeStatus(),
      id: WORK_ID,
      kind: 'web-worker',
      name: 'Retrieve Search Worker',
      ping: () => this.testConnection(),
    });
  }

  getRuntimeStatus() {
    return {
      activeRequestId: this.activeRequestId,
      activeWorker: !!this.activeWorker,
      baseURI: typeof document !== 'undefined' ? document.baseURI : '',
      indexedDBSupported: typeof window !== 'undefined' && typeof window.indexedDB !== 'undefined',
      pendingRequests: this.pendingRequests.size,
      staticUrl: typeof window !== 'undefined' ? String((window as any).BK_STATIC_URL || '') : '',
      userAgent: typeof navigator !== 'undefined' ? navigator.userAgent : '',
      workerSupported: this.workerSupported,
      workerUrl: this.getWorkerUrl(),
    };
  }

  getWorkerUrl() {
    try {
      return new URL('../workers/retrieve-search.worker.ts', import.meta.url).toString();
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      return `resolve-worker-url-failed:${message}`;
    }
  }

  cancelActiveSearch() {
    if (!this.activeRequestId) return;
    const requestId = this.activeRequestId;
    this.activeWorker?.postMessage({ id: requestId, type: 'cancel' });
    const pending = this.pendingRequests.get(requestId);
    if (pending) {
      if (pending.timer) clearTimeout(pending.timer);
      this.pendingRequests.delete(requestId);
      pending.reject(new Error('Search request canceled'));
    }
    this.activeRequestId = null;
  }

  async testConnection(timeout = DEFAULT_DIAGNOSTIC_TIMEOUT) {
    const status = this.getRuntimeStatus();
    if (!this.workerSupported) {
      return { ...status, ok: false, error: 'WebWorker is not supported' };
    }

    let worker: Worker | null = null;
    let timer: ReturnType<typeof setTimeout> | null = null;
    const id = `worker-diagnostic:${Date.now()}`;

    try {
      worker = this.createWorker();
      return await new Promise<any>((resolve) => {
        const cleanup = () => {
          if (timer) clearTimeout(timer);
          if (worker) {
            worker.onmessage = null;
            worker.onerror = null;
            worker.terminate();
            worker = null;
          }
        };

        timer = setTimeout(() => {
          cleanup();
          resolve({ ...status, ok: false, error: `WebWorker diagnostic timeout after ${timeout}ms` });
        }, timeout);

        worker!.onmessage = (event) => {
          if (event.data?.id !== id) return;
          cleanup();
          resolve({ ...status, ok: !!event.data?.ok, message: event.data });
        };

        worker!.onerror = (error) => {
          cleanup();
          resolve({ ...status, ok: false, error: error.message || 'WebWorker script load failed' });
        };

        worker!.postMessage({ id, type: 'ping' });
      });
    } catch (error) {
      if (timer) clearTimeout(timer);
      worker?.terminate();
      return { ...status, ok: false, error: error instanceof Error ? error.message : String(error) };
    }
  }

  async searchStream(request: SearchStreamRequest): Promise<SearchStreamResult> {
    const run = () => this.searchStreamInternal(request);
    const task = this.searchQueue.then(run, run);
    this.searchQueue = task.then(
      () => undefined,
      () => undefined,
    );
    return task;
  }

  private async searchStreamInternal(request: SearchStreamRequest): Promise<SearchStreamResult> {
    const startedAt = Date.now();
    const timeout = request.timeout ?? computeIngestTimeout(8 * 1024 * 1024);

    workerManagerService.incrementMetric(WORK_ID, 'searchStart');
    workerManagerService.update(WORK_ID, {
      metrics: {
        lastQueryKey: request.queryKey,
        lastSearchTimeout: timeout,
        lastWriteMode: request.writeMode || 'replace',
      },
      state: 'running',
      url: this.getWorkerUrl(),
    });

    // logRetrieveSearchIngest('info', 'dispatch search stream to worker', {
    //   queryKey: request.queryKey,
    //   source: 'worker',
    //   stage: 'prepare',
    //   writeMode: request.writeMode,
    // });

    if (!this.workerSupported) {
      throw new Error('WebWorker is not supported');
    }

    const indexedDBUsable = await storageHealthService.ensureIndexedDBUsable();
    if (!indexedDBUsable) {
      storageHealthService.notifyCompatibilityIssue();
      throw new Error('IndexedDB is not usable in WebWorker search');
    }

    const id = `search-stream:${Date.now()}:${Math.random().toString(16).slice(2)}`;
    const worker = this.ensureWorker();
    this.activeRequestId = id;
    const url = buildSearchUrl(request.baseURL, request.searchPath);

    return await new Promise<SearchStreamResult>((resolve, reject) => {
      const cleanupRequest = (shouldResetWorker: boolean) => {
        const pending = this.pendingRequests.get(id);
        if (!pending) return;
        if (pending.timer) clearTimeout(pending.timer);
        this.pendingRequests.delete(id);
        if (this.activeRequestId === id) {
          this.activeRequestId = null;
        }
        if (shouldResetWorker) {
          this.resetWorker('request-failed');
        }
      };

      const timer = setTimeout(() => {
        worker.postMessage({ id, type: 'cancel' });
        cleanupRequest(true);
        const message = `WebWorker search stream timeout after ${timeout}ms`;
        this.recordFailure(message, 'timeout', Date.now() - startedAt, request.queryKey);
        reject(new Error(message));
      }, timeout);

      this.pendingRequests.set(id, { onProgress: request.onProgress, reject, resolve, startedAt, timer });

      try {
        worker.postMessage({
          id,
          body: request.body,
          fieldNames: request.fieldNames || [],
          headers: request.headers || {},
          method: 'POST',
          queryKey: request.queryKey,
          startSeq: request.startSeq || 0,
          type: 'search-stream',
          url,
          writeMode: request.writeMode || 'replace',
        });
      } catch (error) {
        cleanupRequest(true);
        const detail = error instanceof Error ? error.message : String(error);
        this.recordFailure(detail, 'post-message', Date.now() - startedAt, request.queryKey);
        reject(new Error(`Failed to dispatch search stream to WebWorker: ${detail}`));
      }
    });
  }

  private ensureWorker() {
    if (this.activeWorker) return this.activeWorker;
    const worker = this.createWorker();
    worker.onmessage = (event) => this.handleWorkerMessage(event);
    worker.onerror = (error) => this.handleWorkerRuntimeError(error);
    worker.onmessageerror = (error) => this.handleWorkerMessageError(error);
    this.activeWorker = worker;
    return worker;
  }

  private handleWorkerMessage(event: MessageEvent<any>) {
    const message = event.data;
    const id = message?.id;
    if (!id) return;

    if (message.progress) {
      const pending = this.pendingRequests.get(id);
      // logRetrieveSearchIngest('info', `worker search progress: ${message.stage}`, {
      //   queryKey: message.queryKey,
      //   rowCount: message.rowCount,
      //   source: 'worker',
      //   stage: message.stage,
      // });
      pending?.onProgress?.({
        meta: message.meta,
        queryKey: message.queryKey,
        rowCount: message.rowCount,
        rowKeys: message.rowKeys,
        stage: message.stage,
      });
      return;
    }

    const pending = this.pendingRequests.get(id);
    if (!pending) return;

    if (pending.timer) clearTimeout(pending.timer);
    this.pendingRequests.delete(id);
    if (this.activeRequestId === id) {
      this.activeRequestId = null;
    }

    if (!message.ok) {
      const errorCategory = (message.errorCategory || categorizeIngestError(message.error)) as RetrieveSearchIngestErrorCategory;
      this.recordFailure(message.error || 'WebWorker search stream failed', errorCategory, Date.now() - pending.startedAt, message.queryKey, message.timings);
      pending.reject(new Error(message.error || 'WebWorker search stream failed'));
      return;
    }

    workerManagerService.incrementMetric(WORK_ID, 'searchSuccess');
    workerManagerService.update(WORK_ID, {
      lastError: undefined,
      lastOkAt: Date.now(),
      metrics: {
        lastSearchDuration: Date.now() - pending.startedAt,
        lastSearchRows: message.size || 0,
        lastSearchTimings: message.timings || {},
      },
      state: 'idle',
    });

    // logRetrieveSearchIngest('info', 'search stream completed in worker', {
    //   durationMs: Date.now() - pending.startedAt,
    //   rowCount: message.size || 0,
    //   source: 'worker',
    //   stage: 'complete',
    //   timings: message.timings,
    // });

    pending.resolve({
      code: message.response?.code,
      data: message.response?.data || {},
      length: message.size || 0,
      message: message.response?.message,
      permission: message.response?.permission,
      result: !!message.response?.result,
      rowKeys: message.rowKeys || [],
      size: message.size || 0,
      source: 'worker',
      timings: message.timings,
    });
  }

  private handleWorkerRuntimeError(error: ErrorEvent | string) {
    const detail = error instanceof ErrorEvent
      ? `${error.message || 'WebWorker script load failed'}${error.filename ? ` (${error.filename}:${error.lineno}:${error.colno})` : ''}`
      : String(error);
    this.rejectAllPending(new Error(detail), 'worker-load');
    this.resetWorker('runtime-error');
  }

  private handleWorkerMessageError(error: MessageEvent) {
    const detail = `WebWorker message error: ${String(error?.data || error)}`;
    this.rejectAllPending(new Error(detail), 'post-message');
    this.resetWorker('message-error');
  }

  private rejectAllPending(error: Error, category: RetrieveSearchIngestErrorCategory) {
    Array.from(this.pendingRequests.entries()).forEach(([, pending]) => {
      if (pending.timer) clearTimeout(pending.timer);
      this.recordFailure(error.message, category, Date.now() - pending.startedAt);
      pending.reject(error);
    });
    this.pendingRequests.clear();
    this.activeRequestId = null;
  }

  private resetWorker(reason: string) {
    if (!this.activeWorker) return;
    // logRetrieveSearchIngest('warn', `reset retrieve-search worker: ${reason}`, {
    //   pendingRequests: this.pendingRequests.size,
    //   source: 'worker',
    //   stage: 'prepare',
    // });
    this.activeWorker.onmessage = null;
    this.activeWorker.onerror = null;
    this.activeWorker.onmessageerror = null;
    this.activeWorker.terminate();
    this.activeWorker = null;
  }

  private recordFailure(
    message: string,
    errorCategory: RetrieveSearchIngestErrorCategory,
    durationMs: number,
    queryKey?: string,
    timings?: Record<string, number>,
  ) {
    workerManagerService.incrementMetric(WORK_ID, errorCategory === 'timeout' ? 'searchTimeout' : 'searchFailed');
    workerManagerService.update(WORK_ID, {
      lastError: message,
      metrics: {
        lastFailureCategory: errorCategory,
        lastFailureDuration: durationMs,
        lastFailureTimings: timings,
      },
      state: 'error',
    });
    // logRetrieveSearchIngest('warn', message, {
    //   durationMs,
    //   errorCategory,
    //   queryKey,
    //   source: 'worker',
    //   timings,
    // });
  }

  private createWorker() {
    return new Worker(new URL('../workers/retrieve-search.worker.ts', import.meta.url));
  }
}

export const retrieveSearchWorkerService = new RetrieveSearchWorkerService();

// 兼容旧引用
export const retrieveSearchWorkerIngestService = retrieveSearchWorkerService;
