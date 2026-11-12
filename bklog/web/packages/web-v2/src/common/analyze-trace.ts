/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台 (BlueKing PaaS):
 *
 * ---------------------------------------------------
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
 * documentation files (the "Software"), to deal in the Software without restriction, including without limitation
 * the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
 * to permit persons to whom the Software is furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all copies or substantial portions of
 * the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
 * THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
 * CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
 * IN THE SOFTWARE.
 */

export type AnalyzeRecordKind = 'route' | 'branch' | 'action' | 'mutation' | 'http' | 'event' | 'stage';

export interface AnalyzeRecord {
  seq: number;
  ts: number;
  stage: string;
  kind: AnalyzeRecordKind;
  name: string;
  spanId: string;
  parentSpanId?: string;
  traceparent?: string;
  summary?: Record<string, unknown>;
  stateDiff?: Record<string, { before: unknown; after: unknown }>;
}

export interface AnalyzeBuffer {
  enabled: boolean;
  currentStage: string;
  completedStages: string[];
  records: AnalyzeRecord[];
  activeSpanStack: string[];
}

declare global {
  interface Window {
    __BKLOG_ANALYZE__?: AnalyzeBuffer;
  }
}

const SENSITIVE_KEYS = new Set(['bk_token', 'bk_uid', 'cookie', 'authorization', 'token', 'password', 'secret']);

function checkAnalyzeEnabled(): boolean {
  if (typeof window === 'undefined') {
    return false;
  }
  try {
    if (window.localStorage?.getItem('bklog_analyze') === '1') {
      return true;
    }
    const search = window.location.search || '';
    const hashQuery = window.location.hash.includes('?')
      ? window.location.hash.slice(window.location.hash.indexOf('?'))
      : '';
    return (
      new URLSearchParams(search).get('__analyze') === '1' || new URLSearchParams(hashQuery).get('__analyze') === '1'
    );
  } catch {
    return false;
  }
}

let seqCounter = 0;
let spanCounter = 0;

function ensureBuffer(): AnalyzeBuffer | null {
  if (!checkAnalyzeEnabled()) {
    return null;
  }
  if (!window.__BKLOG_ANALYZE__) {
    window.__BKLOG_ANALYZE__ = {
      enabled: true,
      currentStage: 'bootstrap',
      completedStages: [],
      records: [],
      activeSpanStack: [],
    };
  }
  return window.__BKLOG_ANALYZE__;
}

export function isAnalyzeEnabled(): boolean {
  return Boolean(ensureBuffer()?.enabled);
}

export function nextSpanId(prefix = 'sp'): string {
  spanCounter += 1;
  return `${prefix}-${spanCounter}`;
}

export function summarizePayload(input: unknown, depth = 0): Record<string, unknown> | undefined {
  if (input === null || input === undefined) {
    return undefined;
  }
  if (typeof input !== 'object') {
    return { value: String(input).slice(0, 160) };
  }
  if (Array.isArray(input)) {
    return {
      type: 'array',
      length: input.length,
      sampleKeys:
        input.length > 0 && input[0] && typeof input[0] === 'object' ? Object.keys(input[0] as object).slice(0, 8) : [],
    };
  }
  if (depth > 1) {
    return { keys: Object.keys(input as object).slice(0, 12) };
  }
  const out: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(input as Record<string, unknown>).slice(0, 16)) {
    if (SENSITIVE_KEYS.has(k.toLowerCase())) {
      continue;
    }
    if (v === null || v === undefined || typeof v === 'number' || typeof v === 'boolean') {
      out[k] = v;
    } else if (typeof v === 'string') {
      out[k] = v.length > 120 ? `${v.slice(0, 120)}...` : v;
    } else if (Array.isArray(v)) {
      out[k] = `Array(${v.length})`;
    } else if (typeof v === 'object') {
      const obj = v as Record<string, unknown>;
      if ('list' in obj && Array.isArray(obj.list)) {
        out[k] = { total: obj.total ?? obj.list.length, listLen: obj.list.length };
      } else {
        out[k] = { keys: Object.keys(obj).slice(0, 8) };
      }
    }
  }
  return out;
}

const WATCHED_STATE_PATHS: Array<{ key: string; read: (state: any) => unknown }> = [
  { key: 'spaceUid', read: s => s?.spaceUid },
  { key: 'bkBizId', read: s => s?.bkBizId },
  { key: 'indexId', read: s => s?.indexId },
  { key: 'spaceResolveFailed', read: s => s?.spaceResolveFailed },
  { key: 'indexItem.start_time', read: s => s?.indexItem?.start_time },
  { key: 'indexItem.end_time', read: s => s?.indexItem?.end_time },
  { key: 'indexItem.interval', read: s => s?.indexItem?.interval },
  { key: 'indexItem.timezone', read: s => s?.indexItem?.timezone },
  { key: 'indexItem.retrieve_type', read: s => s?.indexItem?.retrieve_type },
  { key: 'indexFieldInfo.is_loading', read: s => s?.indexFieldInfo?.is_loading },
  {
    key: 'indexFieldInfo.fieldsLen',
    read: s => (Array.isArray(s?.indexFieldInfo?.fields) ? s.indexFieldInfo.fields.length : 0),
  },
  { key: 'indexSetQueryResult.is_loading', read: s => s?.indexSetQueryResult?.is_loading },
  {
    key: 'indexSetQueryResult.listLen',
    read: s => (Array.isArray(s?.indexSetQueryResult?.list) ? s.indexSetQueryResult.list.length : 0),
  },
];

export function snapshotWatchedState(state: any): Record<string, unknown> {
  const snap: Record<string, unknown> = {};
  if (!state) return snap;
  for (const item of WATCHED_STATE_PATHS) {
    try {
      snap[item.key] = item.read(state);
    } catch {
      snap[item.key] = undefined;
    }
  }
  return snap;
}

export function diffWatchedState(
  before: Record<string, unknown>,
  after: Record<string, unknown>,
): Record<string, { before: unknown; after: unknown }> | undefined {
  const diff: Record<string, { before: unknown; after: unknown }> = {};
  for (const key of Object.keys(after)) {
    if (before[key] !== after[key]) {
      diff[key] = { before: before[key], after: after[key] };
    }
  }
  return Object.keys(diff).length > 0 ? diff : undefined;
}

export function recordAnalyze(entry: {
  kind: AnalyzeRecordKind;
  name: string;
  stage?: string;
  spanId?: string;
  parentSpanId?: string;
  traceparent?: string;
  summary?: Record<string, unknown>;
  stateDiff?: Record<string, { before: unknown; after: unknown }>;
}): AnalyzeRecord | null {
  const buf = ensureBuffer();
  if (!buf) {
    return null;
  }
  seqCounter += 1;
  const spanId = entry.spanId || nextSpanId(entry.kind);
  // Shared async stacks cannot establish causality across concurrent actions.
  const parentSpanId = entry.parentSpanId;
  const stage = entry.stage || buf.currentStage;
  const rec: AnalyzeRecord = {
    seq: seqCounter,
    ts: Number((typeof performance !== 'undefined' ? performance.now() : Date.now()).toFixed(2)),
    stage,
    kind: entry.kind,
    name: entry.name,
    spanId,
    ...(parentSpanId ? { parentSpanId } : {}),
    ...(entry.traceparent ? { traceparent: entry.traceparent } : {}),
    ...(entry.summary ? { summary: entry.summary } : {}),
    ...(entry.stateDiff ? { stateDiff: entry.stateDiff } : {}),
  };
  buf.records.push(rec);
  try {
    console.info(`[BKLOG_ANALYZE][#${rec.seq}][${rec.stage}][${rec.kind}] ${rec.name}`, rec.summary || '');
  } catch {
    // ignore console errors
  }
  return rec;
}

export function markBranch(name: string, summary?: Record<string, unknown>): AnalyzeRecord | null {
  return recordAnalyze({
    kind: 'branch',
    name,
    summary,
  });
}

export function markStageReady(stageName: string, summary?: Record<string, unknown>): void {
  const buf = ensureBuffer();
  if (!buf) {
    return;
  }
  buf.currentStage = stageName;
  const finalize = () => {
    if (!buf.completedStages.includes(stageName)) {
      buf.completedStages.push(stageName);
    }
    recordAnalyze({
      kind: 'stage',
      name: stageName,
      stage: stageName,
      summary: {
        ...(summary || {}),
        completedStages: [...buf.completedStages],
      },
    });
  };
  if (typeof window !== 'undefined' && typeof window.requestAnimationFrame === 'function') {
    window.requestAnimationFrame(() => finalize());
  } else {
    finalize();
  }
}

export function pushActiveSpan(spanId: string): void {
  const buf = ensureBuffer();
  if (!buf) return;
  buf.activeSpanStack.push(spanId);
}

export function popActiveSpan(spanId: string): void {
  const buf = ensureBuffer();
  if (!buf) return;
  const idx = buf.activeSpanStack.lastIndexOf(spanId);
  if (idx !== -1) {
    buf.activeSpanStack.splice(idx, 1);
  }
}

export function installRouterAnalyze(router: any): void {
  if (!isAnalyzeEnabled() || !router || router.__bklogAnalyzeInstalled) {
    return;
  }
  router.__bklogAnalyzeInstalled = true;
  router.beforeEach((to: any, from: any, next: any) => {
    recordAnalyze({
      kind: 'route',
      name: `beforeEach:${to?.name || to?.path || 'unknown'}`,
      summary: {
        from: from?.fullPath,
        to: to?.fullPath,
        params: to?.params,
        queryKeys: to?.query ? Object.keys(to.query) : [],
      },
    });
    next();
  });
  router.afterEach((to: any) => {
    recordAnalyze({
      kind: 'route',
      name: `afterEach:${to?.name || to?.path || 'unknown'}`,
      summary: {
        fullPath: to?.fullPath,
        name: to?.name,
      },
    });
  });
}

export function installStoreAnalyze(store: any): void {
  if (!isAnalyzeEnabled() || !store || store.__bklogAnalyzeInstalled) {
    return;
  }
  store.__bklogAnalyzeInstalled = true;
  let beforeSnap = snapshotWatchedState(store.state);

  store.subscribe((mutation: { type: string; payload: unknown }, state: any) => {
    const afterSnap = snapshotWatchedState(state);
    const stateDiff = diffWatchedState(beforeSnap, afterSnap);
    beforeSnap = afterSnap;
    recordAnalyze({
      kind: 'mutation',
      name: mutation.type,
      summary: summarizePayload(mutation.payload),
      stateDiff,
    });
    if (mutation.type === 'updateIndexItem' && state?.indexItem?.start_time && state?.indexItem?.end_time) {
      const buf = ensureBuffer();
      if (buf && !buf.completedStages.includes('01-url-resolved') && /^#\/retrieve/.test(window.location.hash)) {
        markStageReady('01-url-resolved', {
          indexId: state.indexId,
          start_time: state.indexItem.start_time,
          end_time: state.indexItem.end_time,
          timezone: state.indexItem.timezone,
        });
      }
    }
  });
}

export default {
  isAnalyzeEnabled,
  recordAnalyze,
  markBranch,
  markStageReady,
  nextSpanId,
  pushActiveSpan,
  popActiveSpan,
  summarizePayload,
  installRouterAnalyze,
  installStoreAnalyze,
};
