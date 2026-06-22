/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 */
import type VueRouter from 'vue-router';

import db from '../core/db';
import {
  performanceRecordRepository,
  type PerformanceRecordEntity,
} from '../repositories/performance-record.repository';
import { workerManagerService } from './worker-manager.service';

const STORAGE_KEY = '__BKLOG_PERFORMANCE_MONITOR_ENABLED__';
const SESSION_KEY = '__BKLOG_PERFORMANCE_MONITOR_SESSION_ID__';
const TAB_ID_KEY = '__BKLOG_PERFORMANCE_MONITOR_TAB_ID__';
const TAB_BIRTH_KEY = '__BKLOG_PERFORMANCE_MONITOR_TAB_BIRTH__';
const TAB_INSTANCE_KEY = '__BKLOG_PERFORMANCE_MONITOR_TAB_INSTANCE__';
const ACTIVE_TABS_KEY = '__BKLOG_PERFORMANCE_MONITOR_ACTIVE_TABS__';
const DEFAULT_SAMPLE_INTERVAL = 1000;
const MAX_BATCH_SIZE = 20;
const MAX_IN_MEMORY_RECORDS = 1000;
const MAX_STACK_LENGTH = 1200;
const ACTIVE_TAB_TTL = 30 * 1000;
const WINDOW_API_NAME = '__BKLOG_PERF_MONITOR__';
const MAX_RESOURCE_SAMPLES = 80;
const MAX_API_SAMPLES = 120;
const MAX_EXPORT_RECORDS = 50000;
const AI_EXPORT_MAX_RECORDS = 12000;
const COMPACT_EXPORT_MAX_RECORDS = 20000;
const MAX_AI_TIMELINE_POINTS = 120;
const MAX_COMPACT_TIMELINE_POINTS = 300;

type MonitorContext = {
  componentPath?: string;
  routeFullPath?: string;
  routeName?: string;
};

type EventCounter = {
  count: number;
  lastStack?: string;
  lastUpdatedAt: number;
};

type TimerCounter = {
  type: 'interval' | 'timeout';
  delay?: number;
  stack?: string;
  createdAt: number;
};

type ApiRequestSample = {
  id: string;
  type: 'fetch' | 'xhr';
  method?: string;
  url: string;
  status?: number;
  duration?: number;
  startTime: number;
  endTime?: number;
  contentLength?: number | null;
  responseType?: string;
  stack?: string;
  error?: string;
};

type ExportState = {
  exporting: boolean;
  startedAt?: number;
  finishedAt?: number;
  stage?: string;
  records?: number;
  filename?: string;
  error?: string;
};

type ExportMode = 'full' | 'compact' | 'ai';

type PerformanceExportOptions = {
  sessionId?: string;
  limit?: number;
  download?: boolean;
  mode?: ExportMode;
  /** full 模式默认保留堆栈；compact / ai 默认移除堆栈，显著降低体积 */
  includeStacks?: boolean;
  /** full 模式默认保留 records；compact / ai 默认不保留原始 records */
  includeRecords?: boolean;
  /** 只导出指定 record type，适用于精准排查 */
  recordTypes?: string[];
  /** sample/sample-detail 按间隔降采样，例如 5 表示每 5 条保留 1 条 */
  sampleEvery?: number;
  /** records 二次限制，优先级高于 limit */
  maxRecords?: number;
  /** 是否格式化 JSON；compact / ai 默认 false */
  pretty?: boolean;
};

type ExportSanitizeOptions = {
  includeStacks: boolean;
  maxStringLength: number;
  maxArrayLength: number;
  maxDepth: number;
};

const safeStringify = (value: any) => {
  try {
    return JSON.stringify(value);
  } catch (error) {
    return `[unserializable: ${String(error)}]`;
  }
};

const getStack = () => {
  const stack = new Error().stack || '';
  return stack.split('\n').slice(2, 12).join('\n').slice(0, MAX_STACK_LENGTH);
};

const getTargetName = (target: any) => {
  if (target === window) return 'window';
  if (target === document) return 'document';
  if (target === document.body) return 'body';
  if (target?.constructor?.name) return target.constructor.name;
  return 'unknown';
};

const getRouteComponentPath = (route: any) => {
  const matched = route?.matched ?? [];
  return matched
    .map((record: any) => {
      const component = record?.components?.default;
      return component?.__file || component?.name || record?.name || record?.path;
    })
    .filter(Boolean)
    .join(' > ');
};

const normalizeUrlForStats = (url = '') => {
  try {
    const target = new URL(url, window.location.href);
    return `${target.origin}${target.pathname}${target.hash.split('?')[0] || ''}`;
  } catch {
    return String(url).split('?')[0];
  }
};

const getContentLength = (headers: Headers | null | undefined) => {
  if (!headers) return null;
  const value = headers.get('content-length') || headers.get('Content-Length');
  const size = Number(value);
  return Number.isFinite(size) ? size : null;
};

const getPerformanceResourceSize = (entry: PerformanceResourceTiming | undefined) => entry
  ? {
      transferSize: entry.transferSize,
      encodedBodySize: entry.encodedBodySize,
      decodedBodySize: entry.decodedBodySize,
      duration: entry.duration,
      initiatorType: entry.initiatorType,
      name: entry.name,
    }
  : null;

const bytesToMB = (value: number | undefined | null) => Number.isFinite(Number(value))
  ? Math.round((Number(value) / 1024 / 1024) * 10) / 10
  : undefined;

const compactRoute = (value = '') => String(value).replace(/([?&](?:keyword|addition|where|query|sql)=[^&]*)/g, (match) => {
  const [key, rawValue = ''] = match.split('=');
  return `${key}=${rawValue.length > 80 ? `${rawValue.slice(0, 80)}...` : rawValue}`;
});

const sanitizeForExport = (value: any, options: ExportSanitizeOptions, depth = 0): any => {
  if (value === null || value === undefined) return value;
  if (typeof value === 'string') return value.length > options.maxStringLength ? `${value.slice(0, options.maxStringLength)}...<truncated:${value.length}>` : value;
  if (typeof value !== 'object') return value;
  if (depth >= options.maxDepth) return Array.isArray(value) ? `[array:${value.length}]` : '[object]';
  if (Array.isArray(value)) {
    return value.slice(0, options.maxArrayLength).map(item => sanitizeForExport(item, options, depth + 1));
  }
  return Object.keys(value).reduce((out, key) => {
    if (!options.includeStacks && /stack|lastStack/i.test(key)) return out;
    out[key] = sanitizeForExport(value[key], options, depth + 1);
    return out;
  }, {} as Record<string, any>);
};

const pickEvery = <T>(list: T[], maxPoints: number) => {
  if (list.length <= maxPoints) return list;
  const step = Math.ceil(list.length / maxPoints);
  return list.filter((_, index) => index % step === 0 || index === list.length - 1);
};


class PerformanceMonitorService {
  private enabled = false;
  private tabId = this.getOrCreateTabId();
  private sessionId = this.getStoredSessionId() || this.createSessionId();
  private sampleTimer: number | null = null;
  private flushTimer: number | null = null;
  private context: MonitorContext = {};
  private pendingRecords: PerformanceRecordEntity[] = [];
  private memoryFallbackRecords: PerformanceRecordEntity[] = [];
  private eventCounters = new Map<string, EventCounter>();
  private timerCounters = new Map<number, TimerCounter>();
  private apiSamples: ApiRequestSample[] = [];
  private windowOpenHistory: Array<{ timestamp: number; url: string; target?: string; normalizedUrl: string; stack?: string }> = [];
  private exportState: ExportState = { exporting: false };
  private eventPatchRestore: null | (() => void) = null;
  private timerPatchRestore: null | (() => void) = null;
  private runtimeObserverRestore: null | (() => void) = null;
  private windowOpenPatchRestore: null | (() => void) = null;
  private pageLifecycleRestore: null | (() => void) = null;
  private networkPatchRestore: null | (() => void) = null;
  private routerInstalled = false;
  private intervalSampleCount = 0;
  private readonly instanceId = `instance:${Date.now()}:${Math.random().toString(16).slice(2)}`;

  init(router?: VueRouter) {
    workerManagerService.register({
      description: '本地性能分析采集 Work：内存、路由、资源、API、window.open、跨 Tab 状态采集与导出',
      getRuntimeStatus: () => ({
        enabled: this.enabled,
        state: this.enabled ? 'running' : 'disabled',
        supported: true,
        sessionId: this.sessionId,
        tabId: this.tabId,
        pendingRecords: this.pendingRecords.length,
        fallbackRecords: this.memoryFallbackRecords.length,
        exportState: this.exportState,
      }),
      id: 'performance-monitor',
      kind: 'runtime-monitor',
      name: 'BKLog Performance Monitor',
    });
    workerManagerService.installGlobalApi();
    this.installGlobalApi();
    if (router) this.bindRouter(router);
    if (this.readEnabledFlag()) {
      this.enable({ reason: 'localStorage' });
    }
  }

  bindRouter(router: VueRouter) {
    if (this.routerInstalled) return;
    this.routerInstalled = true;
    router.afterEach((to) => {
      this.setRouteContext(to);
      this.updateActiveTab('route');
      this.record('route', {
        params: to.params,
        query: to.query,
        componentPath: this.context.componentPath,
      });
      this.collectSample('route-after-each');
    });
    this.setRouteContext(router.currentRoute);
  }

  enable(options: { reason?: string; sampleInterval?: number } = {}) {
    if (this.enabled) return this.status();
    workerManagerService.update('performance-monitor', { state: 'running' });
    this.ensureUniqueTabId();
    this.sessionId = this.ensureSharedSessionId();
    this.enabled = true;
    this.writeEnabledFlag(true);
    this.patchEvents();
    this.patchTimers();
    this.patchWindowOpen();
    this.patchNetwork();
    this.installPageLifecycleObservers();
    this.installRuntimeObservers();
    this.updateActiveTab('enable');
    this.startSampling(options.sampleInterval || DEFAULT_SAMPLE_INTERVAL);
    this.record('monitor-start', { reason: options.reason || 'manual' });
    console.info('[bklog-performance-monitor] enabled', this.status());
    return this.status();
  }

  disable() {
    if (!this.enabled) return this.status();
    workerManagerService.update('performance-monitor', { state: 'disabled' });
    this.record('monitor-stop', {});
    this.enabled = false;
    this.writeEnabledFlag(false);
    this.stopSampling();
    this.removeActiveTab();
    this.restorePatches();
    this.flush();
    console.info('[bklog-performance-monitor] disabled');
    return this.status();
  }

  status() {
    return {
      enabled: this.enabled,
      sessionId: this.sessionId,
      tabId: this.tabId,
      pageId: this.getPageId(),
      activeTabs: this.getActiveTabsSnapshot(),
      route: this.context.routeFullPath,
      routeName: this.context.routeName,
      componentPath: this.context.componentPath,
      pendingRecords: this.pendingRecords.length,
      fallbackRecords: this.memoryFallbackRecords.length,
      eventTypes: this.eventCounters.size,
      events: this.getEventSummary(),
      timers: this.timerCounters.size,
      timersSummary: this.getTimerSnapshot().summary,
      memory: this.getMemorySnapshot(),
      document: this.getDocumentSnapshot(),
      resources: this.getResourceSnapshot(),
      api: this.getApiSnapshot(),
      windowOpen: this.getWindowOpenSnapshot(),
      tabAggregate: this.getTabAggregateSnapshot(),
      workers: workerManagerService.list(),
      exportState: this.exportState,
    };
  }

  mark(name: string, data: any = {}) {
    this.record('mark', { name, data });
    return this.status();
  }

  sample(reason = 'manual') {
    this.collectSample(reason);
    this.collectAsyncSample(reason);
    this.flush();
    return this.status();
  }

  async export(options: PerformanceExportOptions = {}) {
    const mode: ExportMode = options.mode || 'full';
    const sessionId = options.sessionId || this.sessionId;
    const defaultLimit = mode === 'ai' ? AI_EXPORT_MAX_RECORDS : mode === 'compact' ? COMPACT_EXPORT_MAX_RECORDS : MAX_EXPORT_RECORDS;
    const limit = Math.min(options.limit || defaultLimit, options.maxRecords || options.limit || defaultLimit);
    const includeStacks = options.includeStacks ?? mode === 'full';
    const includeRecords = options.includeRecords ?? mode === 'full';
    const pretty = options.pretty ?? mode === 'full';
    this.exportState = { exporting: true, startedAt: Date.now(), stage: 'collect-before-export' };
    console.info('[bklog-performance-monitor] export started', { sessionId, limit, mode, download: options.download !== false });
    this.record('export-start', { sessionId, limit, mode });
    try {
      await this.collectAsyncSample('before-export');
      this.collectSample('before-export-sync');
      this.exportState.stage = 'flush-records';
      await this.flush();
      this.exportState.stage = 'read-records';
      const rawRecords = [
        ...await performanceRecordRepository.list(sessionId, limit),
        ...this.memoryFallbackRecords,
      ];
      const records = this.filterExportRecords(rawRecords, options);
      this.exportState.stage = `build-payload:${mode}`;
      const payload = this.buildExportPayload(records, {
        ...options,
        mode,
        sessionId,
        limit,
        includeStacks,
        includeRecords,
        pretty,
      });
      const filename = `bklog-performance-${mode}-${sessionId}-${Date.now()}.json`;
      this.exportState = {
        exporting: true,
        startedAt: this.exportState.startedAt,
        stage: 'stringify',
        records: records.length,
        filename,
      };
      const content = JSON.stringify(payload, null, pretty ? 2 : 0);
      if (options.download !== false) {
        this.exportState.stage = 'download';
        this.downloadFile(content, filename);
      }
      this.exportState = { exporting: false, startedAt: this.exportState.startedAt, finishedAt: Date.now(), stage: 'done', records: records.length, filename };
      this.record('export-end', { sessionId, records: records.length, filename, mode, bytes: content.length, download: options.download !== false });
      await this.flush();
      console.info('[bklog-performance-monitor] export finished', { ...this.exportState, mode, bytes: content.length });
      return payload;
    } catch (error) {
      this.exportState = { exporting: false, startedAt: this.exportState.startedAt, finishedAt: Date.now(), stage: 'failed', error: String(error) };
      this.record('export-failed', { sessionId, mode, error: String(error) });
      console.error('[bklog-performance-monitor] export failed', error);
      throw error;
    }
  }

  private filterExportRecords(records: PerformanceRecordEntity[], options: PerformanceExportOptions) {
    const typeSet = options.recordTypes?.length ? new Set(options.recordTypes) : null;
    const sampleEvery = Math.max(1, Number(options.sampleEvery || 1));
    let sampleIndex = 0;
    const filtered = records.filter((record) => {
      if (typeSet && !typeSet.has(record.type)) return false;
      if ((record.type === 'sample' || record.type === 'sample-detail') && sampleEvery > 1) {
        sampleIndex += 1;
        return sampleIndex % sampleEvery === 1;
      }
      return true;
    });
    return typeof options.maxRecords === 'number' ? filtered.slice(-options.maxRecords) : filtered;
  }

  private buildExportPayload(records: PerformanceRecordEntity[], options: Required<Pick<PerformanceExportOptions, 'mode' | 'includeStacks' | 'includeRecords' | 'pretty'>> & PerformanceExportOptions) {
    const base = {
      exportedAt: new Date().toISOString(),
      exportMode: options.mode,
      sessionId: options.sessionId || this.sessionId,
      tabId: this.tabId,
      pageId: this.getPageId(),
      userAgent: navigator.userAgent,
      location: window.location.href,
      status: this.getCompactStatus(options.includeStacks),
      summaries: this.buildRecordSummaries(records),
    };

    if (options.mode === 'ai') {
      return this.buildAIExportPayload(base, records, options);
    }

    if (options.mode === 'compact') {
      return {
        ...base,
        activeTabs: this.getActiveTabsSnapshot(),
        tabAggregate: this.getTabAggregateSnapshot(),
        windowOpenSummary: sanitizeForExport(this.getWindowOpenSnapshot(), { includeStacks: options.includeStacks, maxStringLength: 500, maxArrayLength: 80, maxDepth: 5 }),
        resourceSummary: sanitizeForExport(this.getResourceSnapshot(), { includeStacks: false, maxStringLength: 500, maxArrayLength: 80, maxDepth: 5 }),
        apiSummary: sanitizeForExport(this.getApiSnapshot(), { includeStacks: options.includeStacks, maxStringLength: 500, maxArrayLength: 80, maxDepth: 5 }),
        records: options.includeRecords ? this.compactRecords(records, options) : undefined,
      };
    }

    const sanitizeOptions = { includeStacks: options.includeStacks, maxStringLength: 4000, maxArrayLength: 500, maxDepth: 8 };
    return {
      ...base,
      activeTabs: this.getActiveTabsSnapshot(),
      tabAggregate: this.getTabAggregateSnapshot(),
      windowOpenSummary: this.getWindowOpenSnapshot(),
      resourceSummary: this.getResourceSnapshot(),
      apiSummary: this.getApiSnapshot(),
      records: this.compactRecords(records, { ...options, includeStacks: true }).map(record => sanitizeForExport(record, sanitizeOptions)),
    };
  }

  private buildAIExportPayload(base: Record<string, any>, records: PerformanceRecordEntity[], options: PerformanceExportOptions) {
    const summaries = this.buildRecordSummaries(records);
    const memoryTrend = pickEvery(summaries.memoryTrend, MAX_AI_TIMELINE_POINTS);
    const windowOpenRecords = records
      .filter(record => record.type === 'window-open')
      .map(record => this.toAIWindowOpen(record, Boolean(options.includeStacks)));
    const apiHotspots = Object.entries(summaries.apiByUrl)
      .map(([url, stats]: any) => ({ url, ...stats, avgDuration: stats.count ? Math.round(stats.totalDuration / stats.count) : 0 }))
      .sort((a: any, b: any) => (b.contentLength || 0) - (a.contentLength || 0) || (b.totalDuration || 0) - (a.totalDuration || 0))
      .slice(0, 30);
    const routeStats = Object.entries(summaries.routeStats)
      .map(([route, stats]: any) => ({ route, ...stats }))
      .sort((a: any, b: any) => (b.maxHeapMB || 0) - (a.maxHeapMB || 0));
    return {
      ...base,
      format: 'bklog-performance-ai-v1',
      guide: {
        unit: 'memory values are MB when field name ends with MB',
        note: 'This compact AI export removes raw stacks by default and keeps trend, duplicate windows, API/resource hotspots, and evidence records.',
        recommendedPrompt: 'Analyze this BKLog performance export. Focus on memory stair-step, duplicate tabs/window.open, heavy APIs/resources, route changes, and likely source modules.',
      },
      conclusionHints: this.buildConclusionHints(summaries),
      timeline: memoryTrend,
      routeStats,
      windowOpen: {
        count: windowOpenRecords.length,
        records: windowOpenRecords,
        duplicates: summaries.duplicateWindowTargets,
      },
      apiHotspots,
      resourceHotspots: summaries.resourceHotspots,
      errors: summaries.errors.slice(0, 50),
      longTasks: summaries.longTasks.slice(0, 50),
      latestSnapshots: summaries.latestSnapshots,
      evidenceRecords: options.includeRecords ? this.compactRecords(records, { ...options, includeStacks: Boolean(options.includeStacks) }).slice(-300) : undefined,
    };
  }

  private getCompactStatus(includeStacks: boolean) {
    return sanitizeForExport(this.status(), {
      includeStacks,
      maxStringLength: 500,
      maxArrayLength: 80,
      maxDepth: 5,
    });
  }

  private compactRecords(records: PerformanceRecordEntity[], options: Pick<PerformanceExportOptions, 'includeStacks'>) {
    const sanitizeOptions = {
      includeStacks: Boolean(options.includeStacks),
      maxStringLength: options.includeStacks ? 1200 : 500,
      maxArrayLength: 80,
      maxDepth: 6,
    };
    return records.map(record => sanitizeForExport({
      id: record.id,
      type: record.type,
      timestamp: record.timestamp,
      route: compactRoute(record.routeFullPath || ''),
      routeName: record.routeName,
      componentPath: record.componentPath,
      tabId: record.tabId,
      pageId: record.pageId,
      data: record.data,
    }, sanitizeOptions));
  }

  private buildRecordSummaries(records: PerformanceRecordEntity[]) {
    const typeCounts: Record<string, number> = {};
    const routeStats: Record<string, any> = {};
    const apiByUrl: Record<string, any> = {};
    const memoryTrend: any[] = [];
    const errors: any[] = [];
    const longTasks: any[] = [];
    const resourceHotspotsMap: Record<string, any> = {};
    const windowTargetMap: Record<string, any> = {};
    const latestSnapshots: Record<string, any> = {};
    const timeRange = { start: records[0]?.timestamp, end: records[records.length - 1]?.timestamp, durationMs: 0 };
    if (timeRange.start && timeRange.end) timeRange.durationMs = timeRange.end - timeRange.start;

    records.forEach((record) => {
      typeCounts[record.type] = (typeCounts[record.type] || 0) + 1;
      const data: any = record.data || {};
      const memory = data.memory || {};
      const usedHeapMB = bytesToMB(memory.usedJSHeapSize);
      const totalHeapMB = bytesToMB(memory.totalJSHeapSize);
      const route = compactRoute(record.routeFullPath || data.route || data.href || 'unknown');
      const routeItem = routeStats[route] || { count: 0, maxHeapMB: 0, firstAt: record.timestamp, lastAt: record.timestamp, componentPath: record.componentPath };
      routeItem.count += 1;
      routeItem.firstAt = Math.min(routeItem.firstAt, record.timestamp);
      routeItem.lastAt = Math.max(routeItem.lastAt, record.timestamp);
      if (usedHeapMB !== undefined) routeItem.maxHeapMB = Math.max(routeItem.maxHeapMB, usedHeapMB);
      routeStats[route] = routeItem;

      if (record.type === 'sample' || record.type === 'sample-detail') {
        memoryTrend.push({
          t: record.timestamp,
          route,
          routeName: record.routeName,
          tabId: record.tabId,
          usedHeapMB,
          totalHeapMB,
          nodes: data.document?.nodes,
          logRows: data.document?.logRows,
          openWindowCount: data.document?.openWindowCount,
          activeTabs: Array.isArray(data.tabs) ? data.tabs.length : data.tabAggregate?.count,
          reason: data.reason,
        });
        latestSnapshots[record.type] = {
          timestamp: record.timestamp,
          route,
          memory: { usedHeapMB, totalHeapMB },
          document: data.document,
          timers: data.timers?.summary,
          eventSummary: data.eventSummary,
          indexedDB: data.indexedDB,
          tabAggregate: data.tabAggregate,
        };
      }

      if (record.type === 'api-request') {
        const key = normalizeUrlForStats(data.url || '');
        const stats = apiByUrl[key] || { count: 0, errors: 0, totalDuration: 0, maxDuration: 0, contentLength: 0, methods: {} as Record<string, number> };
        stats.count += 1;
        if (data.error || Number(data.status || 0) >= 400) stats.errors += 1;
        stats.totalDuration += Number(data.duration || 0);
        stats.maxDuration = Math.max(stats.maxDuration, Number(data.duration || 0));
        stats.contentLength += Number(data.contentLength || 0);
        const method = data.method || 'GET';
        stats.methods[method] = (stats.methods[method] || 0) + 1;
        apiByUrl[key] = stats;
      }

      if (record.type === 'window-open') {
        const target = data.normalizedUrl || normalizeUrlForStats(data.url || '');
        const item = windowTargetMap[target] || { count: 0, firstAt: record.timestamp, lastAt: record.timestamp, targets: {} as Record<string, number>, recommendation: data.recommendation };
        item.count += 1;
        item.firstAt = Math.min(item.firstAt, record.timestamp);
        item.lastAt = Math.max(item.lastAt, record.timestamp);
        item.targets[data.target || '_blank/empty'] = (item.targets[data.target || '_blank/empty'] || 0) + 1;
        if (data.recommendation) item.recommendation = data.recommendation;
        windowTargetMap[target] = item;
      }

      if (record.type === 'window-error' || record.type === 'unhandled-rejection' || record.type === 'export-failed') {
        errors.push({ timestamp: record.timestamp, type: record.type, route, message: data.message || data.reason || data.error, stack: data.stack });
      }
      if (record.type === 'long-task') {
        longTasks.push({ timestamp: record.timestamp, route, duration: data.duration, name: data.name, attribution: data.attribution });
      }

      const resourceTop = data.resources?.topByDecodedSize || data.resourceSummary?.topByDecodedSize || [];
      resourceTop.forEach((item: any) => {
        const key = item.name || item.shortName;
        if (!key) return;
        const existed = resourceHotspotsMap[key] || { name: key, initiatorType: item.initiatorType, decodedBodySize: 0, transferSize: 0, duration: 0 };
        existed.decodedBodySize = Math.max(existed.decodedBodySize, Number(item.decodedBodySize || 0));
        existed.transferSize = Math.max(existed.transferSize, Number(item.transferSize || 0));
        existed.duration = Math.max(existed.duration, Number(item.duration || 0));
        resourceHotspotsMap[key] = existed;
      });
    });

    const memoryValues = memoryTrend.map(item => item.usedHeapMB).filter((item): item is number => typeof item === 'number');
    const maxHeapMB = memoryValues.length ? Math.max(...memoryValues) : undefined;
    const minHeapMB = memoryValues.length ? Math.min(...memoryValues) : undefined;
    const duplicateWindowTargets = Object.entries(windowTargetMap)
      .filter(([, item]: any) => item.count > 1)
      .map(([url, item]: any) => ({ url, ...item }));
    const resourceHotspots = Object.values(resourceHotspotsMap)
      .sort((a: any, b: any) => Number(b.decodedBodySize || b.transferSize || 0) - Number(a.decodedBodySize || a.transferSize || 0))
      .slice(0, 30);

    return {
      timeRange,
      typeCounts,
      routeStats,
      memory: {
        minHeapMB,
        maxHeapMB,
        deltaHeapMB: maxHeapMB !== undefined && minHeapMB !== undefined ? Math.round((maxHeapMB - minHeapMB) * 10) / 10 : undefined,
        firstHeapMB: memoryTrend[0]?.usedHeapMB,
        lastHeapMB: memoryTrend[memoryTrend.length - 1]?.usedHeapMB,
      },
      memoryTrend: pickEvery(memoryTrend, MAX_COMPACT_TIMELINE_POINTS),
      apiByUrl,
      duplicateWindowTargets,
      resourceHotspots,
      errors,
      longTasks,
      latestSnapshots,
    };
  }

  private toAIWindowOpen(record: PerformanceRecordEntity, includeStacks: boolean) {
    const data: any = record.data || {};
    return sanitizeForExport({
      timestamp: record.timestamp,
      route: compactRoute(record.routeFullPath || ''),
      url: data.url,
      normalizedUrl: data.normalizedUrl,
      target: data.target,
      duplicateTabsCount: Array.isArray(data.duplicateTabs) ? data.duplicateTabs.length : undefined,
      sameUrlOpenCountBefore: data.sameUrlOpenCountBefore,
      recommendation: data.recommendation,
      stack: data.stack,
    }, { includeStacks, maxStringLength: includeStacks ? 1200 : 500, maxArrayLength: 20, maxDepth: 4 });
  }

  private buildConclusionHints(summaries: any) {
    const hints: string[] = [];
    if (summaries.memory?.deltaHeapMB > 500) hints.push(`JS heap changed by about ${summaries.memory.deltaHeapMB}MB during this session.`);
    if (summaries.duplicateWindowTargets?.length) hints.push('Repeated window.open targets were detected; check duplicate Tab creation or stable window name reuse.');
    const apiErrors = Object.entries(summaries.apiByUrl).filter(([, item]: any) => (item as any).errors > 0).length;
    if (apiErrors) hints.push(`${apiErrors} API groups contain failed requests.`);
    if (summaries.resourceHotspots?.length) hints.push('Large resource entries were captured; inspect resourceHotspots for heavy JS chunks/assets.');
    if (summaries.longTasks?.length) hints.push(`${summaries.longTasks.length} long task records were captured.`);
    return hints;
  }


  async clear(options: { sessionId?: string } = {}) {
    await performanceRecordRepository.clear(options.sessionId);
    if (!options.sessionId || options.sessionId === this.sessionId) {
      this.pendingRecords = [];
      this.memoryFallbackRecords = [];
    }
    return this.status();
  }

  private installGlobalApi() {
    const api = {
      enable: (options?: { sampleInterval?: number }) => this.enable({ ...options, reason: 'manual' }),
      disable: () => this.disable(),
      status: () => this.status(),
      sample: (reason?: string) => this.sample(reason),
      mark: (name: string, data?: any) => this.mark(name, data),
      export: (options?: PerformanceExportOptions) => this.export(options),
      clear: (options?: { sessionId?: string }) => this.clear(options),
      worker: () => workerManagerService.ping('retrieve-search-ingest'),
      workerStatus: () => workerManagerService.get('retrieve-search-ingest'),
      workers: () => workerManagerService.list(),
      work: () => workerManagerService.list(),
      help: () => ({
        enable: `${WINDOW_API_NAME}.enable({ sampleInterval: 1000 })`,
        worker: `${WINDOW_API_NAME}.worker() // ping 检索结果解析 WebWorker，检查 worker chunk 是否可加载`,
        workerStatus: `${WINDOW_API_NAME}.workerStatus() // 查看检索解析 WebWorker 状态`,
        workers: 'window.__BKLOG_WORKERS__.list() // 统一查看当前分支内所有 Work / Worker 状态',
        workerNote: '`window.workers` 不是浏览器标准 API；BKLog 统一 Work 管理请使用 `window.__BKLOG_WORKERS__`。',
        disable: `${WINDOW_API_NAME}.disable()`,
        status: `${WINDOW_API_NAME}.status()`,
        sample: `${WINDOW_API_NAME}.sample('manual')`,
        mark: `${WINDOW_API_NAME}.mark('before-search')`,
        export: `${WINDOW_API_NAME}.export()`,
        exportCompact: `${WINDOW_API_NAME}.export({ mode: 'compact' })`,
        exportAI: `${WINDOW_API_NAME}.export({ mode: 'ai' })`,
        exportNoDownload: `${WINDOW_API_NAME}.export({ mode: 'ai', download: false })`,
        clear: `${WINDOW_API_NAME}.clear()`,
        legacyTimer: 'window.__BKLOG_LEGACY_PERF_MONITOR__',
      }),
    };

    const currentApi = (window as any)[WINDOW_API_NAME];
    if (currentApi && currentApi !== api && typeof currentApi.enable !== 'function') {
      (window as any).__BKLOG_LEGACY_PERF_MONITOR__ = currentApi;
    }

    Object.defineProperty(window, WINDOW_API_NAME, {
      configurable: true,
      enumerable: false,
      writable: false,
      value: api,
    });
  }

  private setRouteContext(route: any) {
    this.context = {
      routeFullPath: route?.fullPath || window.location.hash || window.location.pathname,
      routeName: route?.name,
      componentPath: getRouteComponentPath(route),
    };
  }

  private record(type: string, data: any) {
    if (!this.enabled && type !== 'monitor-stop') return;
    const record: PerformanceRecordEntity = {
      sessionId: this.sessionId,
      type,
      timestamp: Date.now(),
      routeFullPath: this.context.routeFullPath || window.location.hash || window.location.pathname,
      routeName: this.context.routeName,
      componentPath: this.context.componentPath,
      tabId: this.tabId,
      pageId: this.getPageId(),
      data: {
        ...data,
        tabId: this.tabId,
        pageId: this.getPageId(),
        href: window.location.href,
        visibilityState: document.visibilityState,
      },
    };
    this.pendingRecords.push(record);
    if (this.pendingRecords.length >= MAX_BATCH_SIZE) this.flush();
  }

  private collectSample(reason: string) {
    this.record('sample', {
      reason,
      memory: this.getMemorySnapshot(),
      document: this.getDocumentSnapshot(),
      events: this.getEventSnapshot(),
      eventSummary: this.getEventSummary(),
      timers: this.getTimerSnapshot(),
      navigation: this.getNavigationSnapshot(),
      resources: this.getResourceSnapshot(),
      api: this.getApiSnapshot(),
      windowOpen: this.getWindowOpenSnapshot(),
      tabs: this.getActiveTabsSnapshot(),
      tabAggregate: this.getTabAggregateSnapshot(),
      workers: workerManagerService.list(),
    });
  }

  private getMemorySnapshot() {
    const memory = (performance as any).memory;
    return memory
      ? {
          jsHeapSizeLimit: memory.jsHeapSizeLimit,
          totalJSHeapSize: memory.totalJSHeapSize,
          usedJSHeapSize: memory.usedJSHeapSize,
        }
      : {
          unsupported: true,
          message: 'performance.memory is only available in Chromium based browsers with compatible settings.',
        };
  }

  private getDocumentSnapshot() {
    return {
      title: document.title,
      visibilityState: document.visibilityState,
      nodes: document.querySelectorAll('*').length,
      scripts: document.scripts.length,
      stylesheets: document.styleSheets.length,
      tippyBoxes: document.querySelectorAll('.tippy-box').length,
      popovers: document.querySelectorAll('.bk-popover,.bk-popover-reference').length,
      logRows: document.querySelectorAll('.bklog-list-row,.bklog-row-container').length,
      collectionDetailLinks: document.querySelectorAll('a[href*="collection-item/manage"],a[href*="collection-item/detail"]').length,
      openWindowCount: this.getOpenWindowCount(),
    };
  }

  private getNavigationSnapshot() {
    const navigation = performance.getEntriesByType?.('navigation')?.[0] as PerformanceNavigationTiming | undefined;
    return navigation
      ? {
          type: navigation.type,
          duration: navigation.duration,
          domComplete: navigation.domComplete,
          loadEventEnd: navigation.loadEventEnd,
        }
      : null;
  }

  private getEventSnapshot() {
    return Array.from(this.eventCounters.entries()).map(([key, value]) => ({ key, ...value }));
  }

  private getEventSummary() {
    return Array.from(this.eventCounters.entries()).reduce((out, [key, value]) => {
      out[key] = value.count;
      return out;
    }, {} as Record<string, number>);
  }

  private getTimerSnapshot() {
    const summary = Array.from(this.timerCounters.values()).reduce((out, item) => {
      const key = item.type;
      out[key] = (out[key] || 0) + 1;
      return out;
    }, {} as Record<string, number>);
    return {
      summary,
      samples: Array.from(this.timerCounters.entries()).slice(-30).map(([id, item]) => ({ id, ...item })),
    };
  }

  private getResourceSnapshot() {
    try {
      const resources = (performance.getEntriesByType?.('resource') || []) as PerformanceResourceTiming[];
      const recent = resources.slice(-MAX_RESOURCE_SAMPLES).map(entry => ({
        name: entry.name,
        shortName: entry.name.slice(0, 240),
        initiatorType: entry.initiatorType,
        duration: entry.duration,
        transferSize: entry.transferSize,
        encodedBodySize: entry.encodedBodySize,
        decodedBodySize: entry.decodedBodySize,
        startTime: entry.startTime,
      }));
      const byType = resources.reduce((out, entry) => {
        const key = entry.initiatorType || 'unknown';
        const item = out[key] || { count: 0, transferSize: 0, encodedBodySize: 0, decodedBodySize: 0 };
        item.count += 1;
        item.transferSize += Number(entry.transferSize || 0);
        item.encodedBodySize += Number(entry.encodedBodySize || 0);
        item.decodedBodySize += Number(entry.decodedBodySize || 0);
        out[key] = item;
        return out;
      }, {} as Record<string, { count: number; transferSize: number; encodedBodySize: number; decodedBodySize: number }>);
      const topByDecodedSize = resources
        .filter(entry => Number(entry.decodedBodySize || entry.transferSize || 0) > 0)
        .sort((a, b) => Number(b.decodedBodySize || b.transferSize || 0) - Number(a.decodedBodySize || a.transferSize || 0))
        .slice(0, 20)
        .map(entry => ({
          name: entry.name,
          initiatorType: entry.initiatorType,
          duration: entry.duration,
          transferSize: entry.transferSize,
          encodedBodySize: entry.encodedBodySize,
          decodedBodySize: entry.decodedBodySize,
        }));
      return { count: resources.length, byType, recent, topByDecodedSize };
    } catch (error) {
      return { error: String(error) };
    }
  }

  private getApiSnapshot() {
    const recent = this.apiSamples.slice(-MAX_API_SAMPLES);
    const byUrl = recent.reduce((out, item) => {
      const key = normalizeUrlForStats(item.url);
      const stats = out[key] || { count: 0, errors: 0, totalDuration: 0, maxDuration: 0, contentLength: 0, methods: {} as Record<string, number> };
      stats.count += 1;
      if (item.error || (item.status && item.status >= 400)) stats.errors += 1;
      stats.totalDuration += Number(item.duration || 0);
      stats.maxDuration = Math.max(stats.maxDuration, Number(item.duration || 0));
      stats.contentLength += Number(item.contentLength || 0);
      const method = item.method || 'GET';
      stats.methods[method] = (stats.methods[method] || 0) + 1;
      out[key] = stats;
      return out;
    }, {} as Record<string, { count: number; errors: number; totalDuration: number; maxDuration: number; contentLength: number; methods: Record<string, number> }>);
    return { count: this.apiSamples.length, recent, byUrl };
  }

  private getWindowOpenSnapshot() {
    const recent = this.windowOpenHistory.slice(-50);
    const byUrl = recent.reduce((out, item) => {
      const current = out[item.normalizedUrl] || { count: 0, targets: {} as Record<string, number>, firstAt: item.timestamp, lastAt: item.timestamp };
      current.count += 1;
      current.targets[item.target || '_blank/empty'] = (current.targets[item.target || '_blank/empty'] || 0) + 1;
      current.firstAt = Math.min(current.firstAt, item.timestamp);
      current.lastAt = Math.max(current.lastAt, item.timestamp);
      out[item.normalizedUrl] = current;
      return out;
    }, {} as Record<string, { count: number; targets: Record<string, number>; firstAt: number; lastAt: number }>);
    return { count: this.windowOpenHistory.length, recent, byUrl };
  }

  private getTabAggregateSnapshot() {
    const tabs = this.getActiveTabsSnapshot().filter((item: any) => !item.error);
    const byRoute = tabs.reduce((out: Record<string, any>, tab: any) => {
      const key = tab.route || tab.href || 'unknown';
      const current = out[key] || { count: 0, visible: 0, hidden: 0, usedJSHeapSizeMax: 0, tabs: [] as string[] };
      current.count += 1;
      if (tab.visibilityState === 'visible') current.visible += 1;
      else current.hidden += 1;
      current.usedJSHeapSizeMax = Math.max(current.usedJSHeapSizeMax, Number(tab.memory?.usedJSHeapSize || 0));
      current.tabs.push(tab.tabId);
      out[key] = current;
      return out;
    }, {});
    const byNormalizedHref = tabs.reduce((out: Record<string, any>, tab: any) => {
      const key = normalizeUrlForStats(tab.href || '');
      const current = out[key] || { count: 0, tabs: [] as string[] };
      current.count += 1;
      current.tabs.push(tab.tabId);
      out[key] = current;
      return out;
    }, {});
    const duplicates = Object.entries(byNormalizedHref)
      .filter(([, value]: any) => value.count > 1)
      .map(([href, value]: any) => ({ href, ...value }));
    return { count: tabs.length, byRoute, duplicates, note: 'performance.memory is process-level in Chromium; identical heap across tabs may represent the same renderer process.' };
  }

  private patchEvents() {
    if (this.eventPatchRestore) return;
    const originalAdd = EventTarget.prototype.addEventListener;
    const originalRemove = EventTarget.prototype.removeEventListener;
    const counters = this.eventCounters;
    const shouldTrace = () => this.enabled;

    EventTarget.prototype.addEventListener = function patchedAdd(type: any, listener: any, options: any) {
      if (shouldTrace()) {
        const targetName = getTargetName(this);
        if (['window', 'document', 'body'].includes(targetName)) {
          const key = `${targetName}:${String(type)}`;
          const current = counters.get(key) || { count: 0, lastUpdatedAt: Date.now() };
          current.count += 1;
          current.lastStack = getStack();
          current.lastUpdatedAt = Date.now();
          counters.set(key, current);
        }
      }
      return originalAdd.call(this, type, listener, options);
    };

    EventTarget.prototype.removeEventListener = function patchedRemove(type: any, listener: any, options: any) {
      if (shouldTrace()) {
        const targetName = getTargetName(this);
        if (['window', 'document', 'body'].includes(targetName)) {
          const key = `${targetName}:${String(type)}`;
          const current = counters.get(key) || { count: 0, lastUpdatedAt: Date.now() };
          current.count = Math.max(0, current.count - 1);
          current.lastUpdatedAt = Date.now();
          counters.set(key, current);
        }
      }
      return originalRemove.call(this, type, listener, options);
    };

    this.eventPatchRestore = () => {
      EventTarget.prototype.addEventListener = originalAdd;
      EventTarget.prototype.removeEventListener = originalRemove;
    };
  }

  private patchTimers() {
    if (this.timerPatchRestore) return;
    const originalSetInterval = window.setInterval;
    const originalClearInterval = window.clearInterval;
    const originalSetTimeout = window.setTimeout;
    const originalClearTimeout = window.clearTimeout;
    const counters = this.timerCounters;

    window.setInterval = ((handler: TimerHandler, timeout?: number, ...args: any[]) => {
      const id = originalSetInterval(handler, timeout, ...args) as unknown as number;
      counters.set(id, { type: 'interval', delay: timeout, stack: getStack(), createdAt: Date.now() });
      return id as any;
    }) as typeof window.setInterval;

    window.clearInterval = ((id?: number) => {
      if (typeof id === 'number') counters.delete(id);
      return originalClearInterval(id);
    }) as typeof window.clearInterval;

    window.setTimeout = ((handler: TimerHandler, timeout?: number, ...args: any[]) => {
      let id = 0;
      if (typeof handler !== 'function') {
        id = originalSetTimeout(handler, timeout, ...args) as unknown as number;
        counters.set(id, { type: 'timeout', delay: timeout, stack: getStack(), createdAt: Date.now() });
        originalSetTimeout(() => counters.delete(id), Number(timeout) || 0);
        return id as any;
      }
      const wrappedHandler = (...handlerArgs: any[]) => {
        counters.delete(id);
        return handler(...handlerArgs);
      };
      id = originalSetTimeout(wrappedHandler, timeout, ...args) as unknown as number;
      counters.set(id, { type: 'timeout', delay: timeout, stack: getStack(), createdAt: Date.now() });
      return id as any;
    }) as typeof window.setTimeout;

    window.clearTimeout = ((id?: number) => {
      if (typeof id === 'number') counters.delete(id);
      return originalClearTimeout(id);
    }) as typeof window.clearTimeout;

    this.timerPatchRestore = () => {
      window.setInterval = originalSetInterval;
      window.clearInterval = originalClearInterval;
      window.setTimeout = originalSetTimeout;
      window.clearTimeout = originalClearTimeout;
    };
  }

  private patchNetwork() {
    if (this.networkPatchRestore) return;
    const originalFetch = window.fetch;
    const originalXhrOpen = XMLHttpRequest.prototype.open;
    const originalXhrSend = XMLHttpRequest.prototype.send;
    const apiSamples = this.apiSamples;
    const recordApi = (sample: ApiRequestSample) => {
      apiSamples.push(sample);
      if (apiSamples.length > MAX_API_SAMPLES * 3) apiSamples.splice(0, apiSamples.length - MAX_API_SAMPLES * 3);
      this.record('api-request', sample);
    };

    if (typeof originalFetch === 'function') {
      window.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
        const start = performance.now();
        const id = `fetch:${Date.now()}:${Math.random().toString(16).slice(2)}`;
        const url = typeof input === 'string' || input instanceof URL ? String(input) : input.url;
        const method = init?.method || (typeof input !== 'string' && !(input instanceof URL) ? input.method : 'GET') || 'GET';
        const stack = getStack();
        try {
          const response = await originalFetch(input as any, init);
          const duration = performance.now() - start;
          const resource = getPerformanceResourceSize(performance.getEntriesByName(url).slice(-1)[0] as PerformanceResourceTiming | undefined);
          recordApi({
            id,
            type: 'fetch',
            method,
            url,
            status: response.status,
            duration,
            startTime: Date.now() - duration,
            endTime: Date.now(),
            contentLength: getContentLength(response.headers) || resource?.decodedBodySize || resource?.transferSize || null,
            stack,
          });
          return response;
        } catch (error) {
          const duration = performance.now() - start;
          recordApi({ id, type: 'fetch', method, url, duration, startTime: Date.now() - duration, endTime: Date.now(), stack, error: String(error) });
          throw error;
        }
      }) as typeof window.fetch;
    }

    XMLHttpRequest.prototype.open = function patchedOpen(method: string, url: string | URL, ...args: any[]) {
      (this as any).__bklogPerfMonitor = {
        id: `xhr:${Date.now()}:${Math.random().toString(16).slice(2)}`,
        method,
        url: String(url),
        stack: getStack(),
      };
      return originalXhrOpen.call(this, method, url as any, ...args as any);
    } as typeof XMLHttpRequest.prototype.open;

    XMLHttpRequest.prototype.send = function patchedSend(...args: any[]) {
      const meta = (this as any).__bklogPerfMonitor || {};
      const start = performance.now();
      const startedAt = Date.now();
      const handleLoadEnd = () => {
        this.removeEventListener('loadend', handleLoadEnd);
        const duration = performance.now() - start;
        let contentLength: number | null = null;
        try {
          const headerValue = this.getResponseHeader('content-length');
          const size = Number(headerValue);
          if (Number.isFinite(size)) contentLength = size;
          else if (typeof this.responseText === 'string') contentLength = this.responseText.length;
        } catch {
          contentLength = null;
        }
        const resource = getPerformanceResourceSize(performance.getEntriesByName(meta.url).slice(-1)[0] as PerformanceResourceTiming | undefined);
        recordApi({
          id: meta.id || `xhr:${startedAt}`,
          type: 'xhr',
          method: meta.method,
          url: meta.url || '',
          status: this.status,
          duration,
          startTime: startedAt,
          endTime: Date.now(),
          contentLength: contentLength || resource?.decodedBodySize || resource?.transferSize || null,
          responseType: this.responseType,
          stack: meta.stack,
        });
      };
      this.addEventListener('loadend', handleLoadEnd);
      return originalXhrSend.apply(this, args as any);
    } as typeof XMLHttpRequest.prototype.send;

    this.networkPatchRestore = () => {
      window.fetch = originalFetch;
      XMLHttpRequest.prototype.open = originalXhrOpen;
      XMLHttpRequest.prototype.send = originalXhrSend;
    };
  }

  private installRuntimeObservers() {
    if (this.runtimeObserverRestore) return;
    const handleError = (event: ErrorEvent) => {
      this.record('window-error', {
        message: event.message,
        filename: event.filename,
        lineno: event.lineno,
        colno: event.colno,
        stack: event.error?.stack?.slice?.(0, 4000),
      });
    };
    const handleRejection = (event: PromiseRejectionEvent) => {
      this.record('unhandled-rejection', {
        reason: String(event.reason),
        stack: event.reason?.stack?.slice?.(0, 4000),
        detail: safeStringify(event.reason).slice(0, 4000),
      });
    };
    window.addEventListener('error', handleError);
    window.addEventListener('unhandledrejection', handleRejection);

    let observer: PerformanceObserver | null = null;
    try {
      if (typeof PerformanceObserver !== 'undefined') {
        observer = new PerformanceObserver((list) => {
          list.getEntries().forEach((entry: any) => {
            this.record('long-task', {
              name: entry.name,
              duration: entry.duration,
              startTime: entry.startTime,
              attribution: entry.attribution,
            });
          });
        });
        observer.observe({ entryTypes: ['longtask'] });
      }
    } catch (error) {
      this.record('long-task-observer-unsupported', { error: String(error) });
    }

    this.runtimeObserverRestore = () => {
      window.removeEventListener('error', handleError);
      window.removeEventListener('unhandledrejection', handleRejection);
      observer?.disconnect();
    };
  }

  private patchWindowOpen() {
    if (this.windowOpenPatchRestore) return;
    const originalOpen = window.open;
    window.open = ((url?: string | URL, target?: string, features?: string) => {
      const href = url === undefined ? '' : String(url);
      const stack = getStack();
      const normalizedUrl = normalizeUrlForStats(href);
      const beforeTabs = this.getActiveTabsSnapshot();
      const duplicateTabs = beforeTabs.filter((tab: any) => normalizeUrlForStats(tab.href || '') === normalizedUrl);
      const sameUrlOpenCount = this.windowOpenHistory.filter(item => item.normalizedUrl === normalizedUrl).length;
      this.windowOpenHistory.push({ timestamp: Date.now(), url: href, target, normalizedUrl, stack });
      this.windowOpenHistory = this.windowOpenHistory.slice(-200);
      this.record('window-open', {
        url: href,
        normalizedUrl,
        target,
        features,
        stack,
        beforeTabs,
        duplicateTabs,
        sameUrlOpenCountBefore: sameUrlOpenCount,
        recommendation: duplicateTabs.length || sameUrlOpenCount ? 'same target URL opened repeatedly; consider stable window name or de-dup guard' : undefined,
      });
      this.collectSample('before-window-open');
      const opened = originalOpen.call(window, url as any, target, features);
      window.setTimeout(() => {
        this.updateActiveTab('after-window-open');
        this.collectSample('after-window-open');
      }, 500);
      return opened;
    }) as typeof window.open;
    this.windowOpenPatchRestore = () => {
      window.open = originalOpen;
    };
  }

  private installPageLifecycleObservers() {
    if (this.pageLifecycleRestore) return;
    const handleVisibilityChange = () => {
      this.updateActiveTab('visibilitychange');
      this.record('page-lifecycle', { event: 'visibilitychange', visibilityState: document.visibilityState });
      this.collectSample(`visibility-${document.visibilityState}`);
    };
    const handlePageShow = (event: PageTransitionEvent) => {
      this.updateActiveTab('pageshow');
      this.record('page-lifecycle', { event: 'pageshow', persisted: event.persisted });
      this.collectSample('pageshow');
    };
    const handlePageHide = (event: PageTransitionEvent) => {
      this.record('page-lifecycle', { event: 'pagehide', persisted: event.persisted });
      this.collectSample('pagehide');
      this.flush();
    };
    const handleFocus = () => {
      this.updateActiveTab('focus');
      this.record('page-lifecycle', { event: 'focus' });
    };
    const handleBlur = () => {
      this.updateActiveTab('blur');
      this.record('page-lifecycle', { event: 'blur' });
    };
    document.addEventListener('visibilitychange', handleVisibilityChange);
    window.addEventListener('pageshow', handlePageShow);
    window.addEventListener('pagehide', handlePageHide);
    window.addEventListener('focus', handleFocus);
    window.addEventListener('blur', handleBlur);
    this.pageLifecycleRestore = () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange);
      window.removeEventListener('pageshow', handlePageShow);
      window.removeEventListener('pagehide', handlePageHide);
      window.removeEventListener('focus', handleFocus);
      window.removeEventListener('blur', handleBlur);
    };
  }

  private restorePatches() {
    this.eventPatchRestore?.();
    this.timerPatchRestore?.();
    this.runtimeObserverRestore?.();
    this.windowOpenPatchRestore?.();
    this.networkPatchRestore?.();
    this.pageLifecycleRestore?.();
    this.eventPatchRestore = null;
    this.timerPatchRestore = null;
    this.runtimeObserverRestore = null;
    this.windowOpenPatchRestore = null;
    this.networkPatchRestore = null;
    this.pageLifecycleRestore = null;
  }

  private startSampling(interval: number) {
    this.stopSampling();
    this.intervalSampleCount = 0;
    this.collectSample('start');
    this.collectAsyncSample('start');
    this.sampleTimer = window.setInterval(() => {
      this.updateActiveTab('interval');
      this.collectSample('interval');
      this.intervalSampleCount += 1;
      if (this.intervalSampleCount % 5 === 0) this.collectAsyncSample('interval-detail');
    }, interval);
    this.flushTimer = window.setInterval(() => this.flush(), Math.max(interval, 5000));
  }

  private stopSampling() {
    if (this.sampleTimer !== null) window.clearInterval(this.sampleTimer);
    if (this.flushTimer !== null) window.clearInterval(this.flushTimer);
    this.sampleTimer = null;
    this.flushTimer = null;
  }

  private async collectAsyncSample(reason: string) {
    if (!this.enabled) return;
    const [storage, indexedDB] = await Promise.all([
      this.getStorageEstimateSnapshot(),
      this.getIndexedDBSnapshot(),
    ]);
    this.record('sample-detail', {
      reason,
      memory: this.getMemorySnapshot(),
      document: this.getDocumentSnapshot(),
      events: this.getEventSnapshot(),
      timers: this.getTimerSnapshot(),
      tabs: this.getActiveTabsSnapshot(),
      tabAggregate: this.getTabAggregateSnapshot(),
      resources: this.getResourceSnapshot(),
      api: this.getApiSnapshot(),
      windowOpen: this.getWindowOpenSnapshot(),
      storage,
      indexedDB,
    });
  }

  private async getStorageEstimateSnapshot() {
    try {
      if (!navigator.storage?.estimate) return { unsupported: true };
      return await navigator.storage.estimate();
    } catch (error) {
      return { error: String(error) };
    }
  }

  private async getIndexedDBSnapshot() {
    try {
      const [retrieveRows, apiCaches, keyValues, performanceRecords] = await Promise.all([
        db.retrieveRows.count(),
        db.apiCaches.count(),
        db.keyValues.count(),
        db.performanceRecords.count(),
      ]);
      const latestMeta = await db.apiCaches
        .where('key')
        .startsWith('api:retrieve/search-result-meta:')
        .reverse()
        .limit(3)
        .toArray();
      return {
        retrieveRows,
        apiCaches,
        keyValues,
        performanceRecords,
        latestSearchMeta: latestMeta.map(item => ({
          key: item.key,
          updatedAt: item.updatedAt,
          row_query_key: item.data?.row_query_key,
          cached_count: item.data?.cached_count,
          rowKeysLength: item.data?.row_keys?.length,
          ingest_source: item.data?.ingest_source,
        })),
      };
    } catch (error) {
      return { error: String(error) };
    }
  }

  private async flush() {
    if (!this.pendingRecords.length) return;
    const records = this.pendingRecords.splice(0, this.pendingRecords.length);
    try {
      await performanceRecordRepository.bulkAdd(records);
    } catch (error) {
      console.warn('[performance-monitor] flush failed', error);
      this.memoryFallbackRecords.push(...records);
      if (this.memoryFallbackRecords.length > MAX_IN_MEMORY_RECORDS) {
        this.memoryFallbackRecords.splice(0, this.memoryFallbackRecords.length - MAX_IN_MEMORY_RECORDS);
      }
    }
  }

  private downloadFile(content: string, filename: string) {
    const blob = new Blob([content], { type: 'application/json;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  }

  private getPageId() {
    return `${this.sessionId}:${this.tabId}`;
  }

  private getOpenWindowCount() {
    return this.getActiveTabsSnapshot().length;
  }

  private createTabId() {
    return `tab:${Date.now()}:${Math.random().toString(16).slice(2)}`;
  }

  private getOrCreateTabId() {
    try {
      const existed = sessionStorage.getItem(TAB_ID_KEY);
      if (existed) return existed;
      const tabId = this.createTabId();
      sessionStorage.setItem(TAB_ID_KEY, tabId);
      sessionStorage.setItem(TAB_BIRTH_KEY, String(Date.now()));
      sessionStorage.setItem(TAB_INSTANCE_KEY, this.instanceId);
      return tabId;
    } catch (error) {
      return `${this.createTabId()}:${String(error).slice(0, 24)}`;
    }
  }

  /**
   * Chrome/Edge 会在 window.open 新标签时复制 opener 的 sessionStorage。
   * 如果直接复用 sessionStorage 中的 tabId，多 Tab 监控会全部归到同一个 tab，
   * activeTabs 只能看到 1 个，无法定位“连续打开采集详情 Tab 导致内存阶跃”的责任页面。
   * 这里通过每个 JS VM 实例唯一的 instanceId 识别 sessionStorage 是否来自旧 Tab，
   * 若发现 cloned sessionStorage，则立即重生成 tabId。
   */
  private ensureUniqueTabId() {
    try {
      const storedInstance = sessionStorage.getItem(TAB_INSTANCE_KEY);
      if (storedInstance === this.instanceId) return;
      const previousTabId = sessionStorage.getItem(TAB_ID_KEY) || this.tabId;
      const tabId = this.createTabId();
      this.tabId = tabId;
      sessionStorage.setItem(TAB_ID_KEY, tabId);
      sessionStorage.setItem(TAB_BIRTH_KEY, String(Date.now()));
      sessionStorage.setItem(TAB_INSTANCE_KEY, this.instanceId);
      if (previousTabId && previousTabId !== tabId) {
        this.record('tab-id-renewed', { previousTabId, tabId, reason: storedInstance ? 'cloned-sessionStorage' : 'new-instance' });
      }
    } catch (error) {
      this.tabId = `${this.createTabId()}:${String(error).slice(0, 24)}`;
    }
  }

  private getStoredSessionId() {
    try {
      return localStorage.getItem(SESSION_KEY) || '';
    } catch {
      return '';
    }
  }

  private ensureSharedSessionId() {
    const existed = this.getStoredSessionId();
    if (existed) return existed;
    const sessionId = this.createSessionId();
    try {
      localStorage.setItem(SESSION_KEY, sessionId);
    } catch (error) {
      console.warn('[performance-monitor] write shared session failed', error);
    }
    return sessionId;
  }

  private getActiveTabsSnapshot() {
    try {
      const now = Date.now();
      const raw = JSON.parse(localStorage.getItem(ACTIVE_TABS_KEY) || '{}');
      return Object.entries(raw)
        .map(([tabId, info]: any) => ({ tabId, ...info }))
        .filter((item: any) => now - Number(item.updatedAt || 0) < ACTIVE_TAB_TTL);
    } catch (error) {
      return [{ error: String(error), tabId: this.tabId }];
    }
  }

  private updateActiveTab(reason: string) {
    try {
      const now = Date.now();
      const raw = JSON.parse(localStorage.getItem(ACTIVE_TABS_KEY) || '{}');
      Object.keys(raw).forEach((tabId) => {
        if (now - Number(raw[tabId]?.updatedAt || 0) >= ACTIVE_TAB_TTL) delete raw[tabId];
      });
      raw[this.tabId] = {
        sessionId: this.sessionId,
        updatedAt: now,
        reason,
        href: window.location.href,
        route: this.context.routeFullPath,
        routeName: this.context.routeName,
        visibilityState: document.visibilityState,
        memory: this.getMemorySnapshot(),
      };
      localStorage.setItem(ACTIVE_TABS_KEY, JSON.stringify(raw));
    } catch (error) {
      this.record('active-tab-update-failed', { reason, error: String(error) });
    }
  }

  private removeActiveTab() {
    try {
      const raw = JSON.parse(localStorage.getItem(ACTIVE_TABS_KEY) || '{}');
      delete raw[this.tabId];
      localStorage.setItem(ACTIVE_TABS_KEY, JSON.stringify(raw));
    } catch (error) {
      this.record('active-tab-remove-failed', { error: String(error) });
    }
  }

  private createSessionId() {
    const suffix = typeof crypto !== 'undefined' && crypto.randomUUID
      ? crypto.randomUUID()
      : Math.random().toString(16).slice(2);
    return `perf:${Date.now()}:${suffix}`;
  }

  private readEnabledFlag() {
    try {
      return localStorage.getItem(STORAGE_KEY) === '1';
    } catch {
      return false;
    }
  }

  private writeEnabledFlag(enabled: boolean) {
    try {
      if (enabled) localStorage.setItem(STORAGE_KEY, '1');
      else localStorage.removeItem(STORAGE_KEY);
    } catch (error) {
      console.warn('[performance-monitor] write enabled flag failed', error);
    }
  }
}

export const performanceMonitorService = new PerformanceMonitorService();
