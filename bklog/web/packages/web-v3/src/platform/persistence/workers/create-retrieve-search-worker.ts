/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 */

import compiledWorkerUrl from './retrieve-search.worker.ts?worker&url';

export const createRetrieveSearchWorker = () => new Worker(new URL('./retrieve-search.worker.ts', import.meta.url), { type: 'module' });

export const getRetrieveSearchWorkerUrl = () => {
  try {
    return new URL(compiledWorkerUrl, import.meta.url).toString();
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    return `resolve-worker-url-failed:${message}`;
  }
};
