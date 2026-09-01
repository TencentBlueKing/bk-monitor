/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 * License for 蓝鲸智云PaaS平台 (BlueKing PaaS):
 * ---------------------------------------------------
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
 * documentation files (the "Software"), to deal in the Software without restriction, including without limitation
 * the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
 * to permit persons to whom the Software is furnished to do so, subject to the following conditions:
 * The above copyright notice and this permission notice shall be included in all copies or substantial portions of
 * the Software.
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
 * THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
 * CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
 * IN THE SOFTWARE.
 */

import { workerManagerService } from './worker-manager.service';
import { createClusterTableWorker, getClusterTableWorkerUrl } from '../workers/create-cluster-table-worker';
import {
  buildClusterView,
  runClusterTablePipeline,
  toPlainPipelineInput,
  toPlainWindowOptions,
  type ClusterPipelineInput,
  type ClusterViewResult,
  type ITableItem,
  type WalkVisibleWindowOptions,
} from '../workers/cluster-table-pipeline';

const WORK_ID = 'cluster-table-pipeline';

interface PendingRequest {
  reject: (_error: Error) => void;
  resolve: (_value: ClusterViewResult | true) => void;
  timer: ReturnType<typeof setTimeout> | null;
}

class ClusterTableWorkerService {
  private workerSupported = typeof Worker !== 'undefined' && typeof URL !== 'undefined';
  private activeWorker: Worker | null = null;
  private pendingRequests = new Map<string, PendingRequest>();
  private requestSeq = 0;
  private workerHasRaw = false;
  private localSnapshot: ITableItem[] = [];
  private localCounts = { childCount: 0, groupCount: 0, visibleCount: 0 };
  private ownsInWorker = false;

  constructor() {
    workerManagerService.register({
      description: '日志聚类表格分组 / 排序 / 过滤 WebWorker',
      getRuntimeStatus: () => this.getRuntimeStatus(),
      id: WORK_ID,
      kind: 'web-worker',
      name: 'Cluster Table Worker',
      ping: () => this.ping(),
      url: getClusterTableWorkerUrl(),
    });
  }

  getRuntimeStatus() {
    return {
      activeWorker: !!this.activeWorker,
      ownsInWorker: this.ownsInWorker,
      pendingRequests: this.pendingRequests.size,
      workerHasRaw: this.workerHasRaw,
      workerSupported: this.workerSupported,
      workerUrl: getClusterTableWorkerUrl(),
    };
  }

  async ping() {
    if (!this.workerSupported) {
      return { ok: false, error: 'WebWorker is not supported' };
    }
    try {
      await this.postMessage({ type: 'ping' }, 3000);
      workerManagerService.update(WORK_ID, { lastOkAt: Date.now(), lastPingAt: Date.now(), state: 'idle' });
      return { ok: true };
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      workerManagerService.update(WORK_ID, { lastError: message, lastPingAt: Date.now(), state: 'error' });
      return { ok: false, error: message };
    }
  }

  async run(
    input: ClusterPipelineInput,
    windowOptions: WalkVisibleWindowOptions,
  ): Promise<{ viaWorker: boolean; view: ClusterViewResult }> {
    const plainWindow = toPlainWindowOptions(windowOptions);
    const sendRaw = !this.workerHasRaw || !this.ownsInWorker;
    const plainInput = toPlainPipelineInput(input, sendRaw);

    if (this.workerSupported) {
      try {
        workerManagerService.update(WORK_ID, { state: 'running' });
        const view = (await this.postMessage(
          {
            payload: plainInput,
            type: 'pipeline',
            window: plainWindow,
          },
          30000,
        )) as ClusterViewResult;
        this.ownsInWorker = true;
        this.workerHasRaw = true;
        this.localSnapshot = [];
        workerManagerService.update(WORK_ID, { lastOkAt: Date.now(), state: 'idle' });
        workerManagerService.incrementMetric(WORK_ID, 'pipelineCount');
        return { viaWorker: true, view };
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        workerManagerService.update(WORK_ID, { lastError: message, state: 'error' });
        console.warn('[cluster-table-worker] fallback to main thread', error);
        this.destroyWorker();
      }
    }

    return { viaWorker: false, view: this.runLocal(toPlainPipelineInput(input, true), plainWindow) };
  }

  async walk(windowOptions: WalkVisibleWindowOptions): Promise<{ viaWorker: boolean; view: ClusterViewResult }> {
    const plainWindow = toPlainWindowOptions(windowOptions);
    if (this.ownsInWorker && this.workerSupported) {
      try {
        const view = (await this.postMessage({ type: 'walk', window: plainWindow }, 8000)) as ClusterViewResult;
        return { viaWorker: true, view };
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        workerManagerService.update(WORK_ID, { lastError: message, state: 'error' });
        console.warn('[cluster-table-worker] walk fallback to main thread', error);
        this.destroyWorker();
      }
    }
    return {
      viaWorker: false,
      view: buildClusterView(this.localSnapshot, this.localCounts, plainWindow),
    };
  }

  async clear() {
    this.localSnapshot = [];
    this.localCounts = { childCount: 0, groupCount: 0, visibleCount: 0 };
    this.workerHasRaw = false;
    this.ownsInWorker = false;
    if (!this.activeWorker) return;
    try {
      await this.postMessage({ type: 'clear' }, 3000);
    } catch (error) {
      this.destroyWorker();
    }
  }

  private runLocal(input: ClusterPipelineInput, windowOptions: WalkVisibleWindowOptions): ClusterViewResult {
    const result = runClusterTablePipeline({
      ...input,
      raw: input.raw ?? [],
    });
    this.localSnapshot = result.list;
    this.localCounts = {
      childCount: result.childCount,
      groupCount: result.groupCount,
      visibleCount: result.visibleCount,
    };
    this.ownsInWorker = false;
    this.workerHasRaw = false;
    return buildClusterView(this.localSnapshot, this.localCounts, windowOptions);
  }

  private destroyWorker() {
    this.pendingRequests.forEach(pending => {
      if (pending.timer) clearTimeout(pending.timer);
    });
    this.pendingRequests.clear();
    this.activeWorker?.terminate();
    this.activeWorker = null;
    this.ownsInWorker = false;
    this.workerHasRaw = false;
  }

  private ensureWorker() {
    if (this.activeWorker) return this.activeWorker;
    const worker = createClusterTableWorker();
    worker.onmessage = (event: MessageEvent) => {
      const data = event.data || {};
      const pending = this.pendingRequests.get(data.id);
      if (!pending) return;
      if (pending.timer) clearTimeout(pending.timer);
      this.pendingRequests.delete(data.id);
      if (data.ok) {
        pending.resolve(data.type === 'pong' || data.type === 'cleared' ? true : data.result);
      } else {
        pending.reject(new Error(data.error || 'cluster table worker failed'));
      }
    };
    worker.onerror = event => {
      const error = new Error(event.message || 'cluster table worker error');
      this.pendingRequests.forEach(pending => {
        if (pending.timer) clearTimeout(pending.timer);
        pending.reject(error);
      });
      this.pendingRequests.clear();
      this.activeWorker = null;
      this.ownsInWorker = false;
      this.workerHasRaw = false;
    };
    worker.addEventListener?.('messageerror', () => {
      this.pendingRequests.forEach(pending => {
        if (pending.timer) clearTimeout(pending.timer);
        pending.reject(new Error('cluster table worker messageerror'));
      });
      this.pendingRequests.clear();
    });
    this.activeWorker = worker;
    return worker;
  }

  private postMessage(
    body: {
      payload?: ClusterPipelineInput;
      type: 'clear' | 'ping' | 'pipeline' | 'walk';
      window?: WalkVisibleWindowOptions;
    },
    timeout: number,
  ) {
    const requestSeq = this.requestSeq;
    this.requestSeq += 1;
    const id = `cluster-table:${Date.now()}:${requestSeq}`;
    const worker = this.ensureWorker();
    return new Promise<ClusterViewResult | true>((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pendingRequests.delete(id);
        reject(new Error(`cluster table worker timeout: ${body.type}`));
      }, timeout);
      this.pendingRequests.set(id, { reject, resolve, timer });
      try {
        worker.postMessage({ id, ...body });
      } catch (error) {
        this.pendingRequests.delete(id);
        clearTimeout(timer);
        reject(error instanceof Error ? error : new Error(String(error)));
      }
    });
  }
}

export const clusterTableWorkerService = new ClusterTableWorkerService();
