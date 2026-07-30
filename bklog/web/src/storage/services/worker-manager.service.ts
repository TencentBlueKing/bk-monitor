/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 */

type WorkState = 'disabled' | 'error' | 'idle' | 'loading' | 'running' | 'unsupported';

type WorkKind = 'runtime-monitor' | 'web-worker';

export interface ManagedWorkRuntimeStatus {
  enabled?: boolean;
  supported?: boolean;
  state?: WorkState;
  url?: string;
  [key: string]: any;
}

export interface ManagedWorkPingResult {
  ok: boolean;
  error?: string;
  [key: string]: any;
}

export interface ManagedWorkDefinition {
  description?: string;
  getRuntimeStatus?: () => ManagedWorkRuntimeStatus;
  id: string;
  kind: WorkKind;
  name: string;
  ping?: () => Promise<ManagedWorkPingResult> | ManagedWorkPingResult;
  url?: string;
}

export interface ManagedWorkSnapshot {
  createdAt: number;
  description?: string;
  enabled: boolean;
  id: string;
  kind: WorkKind;
  lastError?: string;
  lastOkAt?: number;
  lastPingAt?: number;
  metrics: Record<string, any>;
  name: string;
  state: WorkState;
  supported: boolean;
  updatedAt: number;
  url?: string;
}

type ManagedWorkEntry = ManagedWorkDefinition & {
  createdAt: number;
  lastError?: string;
  lastOkAt?: number;
  lastPingAt?: number;
  metrics: Record<string, any>;
  state: WorkState;
  updatedAt: number;
};

const WINDOW_WORKERS_API_NAME = '__BKLOG_WORKERS__';
const WINDOW_WORKER_MANAGER_API_NAME = '__BKLOG_WORKER_MANAGER__';

const toErrorMessage = (error: any) => error instanceof Error ? error.message : String(error);

class WorkerManagerService {
  private works = new Map<string, ManagedWorkEntry>();

  installGlobalApi() {
    if (typeof window === 'undefined') return;

    const api = {
      get: (id: string) => this.get(id),
      help: () => ({
        list: `${WINDOW_WORKERS_API_NAME}.list() // 查看当前注册的 Work / Worker 状态`,
        status: `${WINDOW_WORKERS_API_NAME}.status() // 同 list()，返回 search-ingest worker 和 performance-monitor 状态`,
        get: `${WINDOW_WORKERS_API_NAME}.get('retrieve-search-ingest')`,
        ping: `${WINDOW_WORKERS_API_NAME}.ping('retrieve-search-ingest') // 创建并 ping 指定 WebWorker`,
        pingAll: `${WINDOW_WORKERS_API_NAME}.pingAll() // ping 所有支持 ping 的 Work`,
        note: '`window.workers` 不是浏览器标准 API；BKLog 统一 Work 管理请使用 window.__BKLOG_WORKERS__。',
      }),
      list: () => this.list(),
      ping: (id: string) => this.ping(id),
      pingAll: () => this.pingAll(),
      status: () => this.list(),
    };

    Object.defineProperty(window, WINDOW_WORKERS_API_NAME, {
      configurable: true,
      enumerable: false,
      value: api,
      writable: false,
    });

    Object.defineProperty(window, WINDOW_WORKER_MANAGER_API_NAME, {
      configurable: true,
      enumerable: false,
      value: api,
      writable: false,
    });
  }

  register(definition: ManagedWorkDefinition) {
    const existed = this.works.get(definition.id);
    const now = Date.now();
    this.works.set(definition.id, {
      ...existed,
      ...definition,
      createdAt: existed?.createdAt ?? now,
      metrics: existed?.metrics ?? {},
      state: existed?.state ?? 'idle',
      updatedAt: now,
    });
    return this.get(definition.id);
  }

  update(id: string, patch: Partial<Pick<ManagedWorkEntry, 'lastError' | 'lastOkAt' | 'lastPingAt' | 'state' | 'url'>> & { metrics?: Record<string, any> }) {
    const entry = this.works.get(id);
    if (!entry) return null;
    const nextMetrics = patch.metrics ? { ...entry.metrics, ...patch.metrics } : entry.metrics;
    this.works.set(id, {
      ...entry,
      ...patch,
      metrics: nextMetrics,
      updatedAt: Date.now(),
    });
    return this.get(id);
  }

  incrementMetric(id: string, key: string, step = 1) {
    const entry = this.works.get(id);
    if (!entry) return null;
    return this.update(id, {
      metrics: {
        [key]: Number(entry.metrics?.[key] || 0) + step,
      },
    });
  }

  get(id: string): ManagedWorkSnapshot | null {
    const entry = this.works.get(id);
    if (!entry) return null;
    return this.toSnapshot(entry);
  }

  list() {
    return Array.from(this.works.values()).map(entry => this.toSnapshot(entry));
  }

  async ping(id: string) {
    const entry = this.works.get(id);
    if (!entry) {
      return { error: `Work not found: ${id}`, id, ok: false };
    }
    if (!entry.ping) {
      const snapshot = this.toSnapshot(entry);
      return { id, ok: true, skipped: true, reason: 'ping is not supported', snapshot };
    }

    this.update(id, { state: 'loading' });
    const startedAt = Date.now();
    try {
      const result = await entry.ping();
      const duration = Date.now() - startedAt;
      this.update(id, {
        lastError: result.ok ? undefined : result.error,
        lastOkAt: result.ok ? Date.now() : entry.lastOkAt,
        lastPingAt: Date.now(),
        metrics: {
          lastPingDuration: duration,
          pingFailed: Number(entry.metrics?.pingFailed || 0) + (result.ok ? 0 : 1),
          pingSuccess: Number(entry.metrics?.pingSuccess || 0) + (result.ok ? 1 : 0),
        },
        state: result.ok ? 'idle' : 'error',
      });
      return { ...result, duration, id, snapshot: this.get(id) };
    } catch (error) {
      const duration = Date.now() - startedAt;
      const message = toErrorMessage(error);
      this.update(id, {
        lastError: message,
        lastPingAt: Date.now(),
        metrics: {
          lastPingDuration: duration,
          pingFailed: Number(entry.metrics?.pingFailed || 0) + 1,
        },
        state: 'error',
      });
      return { duration, error: message, id, ok: false, snapshot: this.get(id) };
    }
  }

  async pingAll() {
    const ids = Array.from(this.works.keys());
    const results = await Promise.all(ids.map(id => this.ping(id)));
    return {
      results,
      summary: {
        failed: results.filter(item => !item.ok).length,
        skipped: results.filter((item: any) => item.skipped).length,
        total: results.length,
      },
    };
  }

  private toSnapshot(entry: ManagedWorkEntry): ManagedWorkSnapshot {
    const runtime = entry.getRuntimeStatus?.() || {};
    const supported = runtime.supported ?? runtime.workerSupported ?? true;
    const enabled = runtime.enabled ?? entry.state !== 'disabled';
    const state = runtime.state || (!supported ? 'unsupported' : entry.state);

    return {
      createdAt: entry.createdAt,
      description: entry.description,
      enabled: !!enabled,
      id: entry.id,
      kind: entry.kind,
      lastError: entry.lastError,
      lastOkAt: entry.lastOkAt,
      lastPingAt: entry.lastPingAt,
      metrics: { ...entry.metrics },
      name: entry.name,
      state,
      supported: !!supported,
      updatedAt: entry.updatedAt,
      url: runtime.url || runtime.workerUrl || entry.url,
      ...runtime,
    };
  }
}

export const workerManagerService = new WorkerManagerService();
