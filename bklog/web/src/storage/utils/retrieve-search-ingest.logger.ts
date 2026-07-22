/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 */

export const RETRIEVE_SEARCH_INGEST_LOG_PREFIX = '[retrieve-search-ingest]';

export type RetrieveSearchIngestStage =
  | 'decode'
  | 'fallback'
  | 'fetch'
  | 'parse'
  | 'post-message'
  | 'prepare'
  | 'start'
  | 'write'
  | 'complete';

export type RetrieveSearchIngestErrorCategory =
  | 'indexeddb'
  | 'invalid-response'
  | 'parse'
  | 'post-message'
  | 'timeout'
  | 'unknown'
  | 'unsupported'
  | 'worker-load'
  | 'worker-message';

export interface RetrieveSearchIngestLogContext {
  blobBytes?: number;
  durationMs?: number;
  errorCategory?: RetrieveSearchIngestErrorCategory;
  listLength?: number;
  originLogListLength?: number;
  queryKey?: string;
  rowCount?: number;
  source?: 'main-thread' | 'worker';
  stage?: RetrieveSearchIngestStage;
  textBytes?: number;
  timings?: Record<string, number>;
  writeMode?: string;
}

const MIN_INGEST_TIMEOUT = 120000;
const MAX_INGEST_TIMEOUT = 600000;
const TIMEOUT_BYTES_PER_MS = 64 * 1024;

export function formatBytes(bytes?: number) {
  if (typeof bytes !== 'number' || Number.isNaN(bytes)) return 'unknown';
  if (bytes < 1024) return `${bytes}B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)}MB`;
}

export function computeIngestTimeout(blobBytes = 0) {
  const sizeBasedTimeout = Math.ceil(blobBytes / TIMEOUT_BYTES_PER_MS);
  return Math.min(MAX_INGEST_TIMEOUT, Math.max(MIN_INGEST_TIMEOUT, sizeBasedTimeout));
}

export function categorizeIngestError(error: unknown): RetrieveSearchIngestErrorCategory {
  const message = error instanceof Error ? error.message : String(error);
  const normalized = message.toLowerCase();

  if (normalized.includes('timeout')) return 'timeout';
  if (normalized.includes('indexeddb') || normalized.includes('quota')) return 'indexeddb';
  if (normalized.includes('not supported')) return 'unsupported';
  if (normalized.includes('script load failed') || normalized.includes('importscripts')) return 'worker-load';
  if (normalized.includes('message error') || normalized.includes('messageerror')) return 'post-message';
  if (normalized.includes('invalid search response')) return 'invalid-response';
  if (
    normalized.includes('json')
    || normalized.includes('unexpected token')
    || normalized.includes('parse')
    || normalized.includes('decode')
  ) {
    return 'parse';
  }
  if (normalized.includes('webworker')) return 'worker-message';
  return 'unknown';
}

export function logRetrieveSearchIngest(
  level: 'info' | 'warn' | 'error',
  message: string,
  context: RetrieveSearchIngestLogContext = {},
) {
  const payload = {
    ...context,
    blobSize: formatBytes(context.blobBytes),
    textSize: formatBytes(context.textBytes),
  };
  const logger = level === 'error' ? console.error : level === 'warn' ? console.warn : console.info;
  logger(`${RETRIEVE_SEARCH_INGEST_LOG_PREFIX} ${message}`, payload);
}
