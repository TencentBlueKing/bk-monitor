/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 */
import { storageHealthService } from './storage-health.service';

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

const DEFAULT_TIMEOUT = 120000;

class RetrieveSearchWorkerIngestService {
  private workerSupported = typeof Worker !== 'undefined' && typeof URL !== 'undefined';

  async ingestBlob(blob: Blob, options: WorkerIngestOptions): Promise<WorkerIngestResult> {
    if (!this.workerSupported) {
      storageHealthService.notifyCompatibilityIssue('当前浏览器不支持 WebWorker，本次检索将使用主线程解析；功能不受影响，但大数据检索期间页面可能短暂卡顿。');
      throw new Error('WebWorker is not supported');
    }

    const indexedDBUsable = await storageHealthService.ensureIndexedDBUsable();
    if (!indexedDBUsable) {
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
          reject(new Error('WebWorker search ingest timeout'));
        }, options.timeout ?? DEFAULT_TIMEOUT);

        worker!.onmessage = (event: MessageEvent<any>) => {
          const message = event.data;
          if (message?.id !== id) return;
          cleanupWorker();

          if (!message.ok) {
            reject(new Error(message.error || 'WebWorker search ingest failed'));
            return;
          }

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
          cleanupWorker();
          reject(error instanceof ErrorEvent ? new Error(error.message) : error);
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
      throw error;
    }
  }

  private createWorker() {
    return new Worker(new URL('../workers/retrieve-search-ingest.worker.ts', import.meta.url));
  }
}

export const retrieveSearchWorkerIngestService = new RetrieveSearchWorkerIngestService();
