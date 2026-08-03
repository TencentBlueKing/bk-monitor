/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * 仅用于 Monitor 嵌入构建：通过 worker-loader 将 Worker 内联为 Blob，
 * 宿主无需再单独托管 worker chunk 文件。
 *
 * monitor-inline-worker-loader 是 worker-loader 的包装，由 scripts/create-monitor.js
 * 通过 resolveLoader.alias 注入，作用是让 Worker 子编译不继承本构建的 commonjs externals。
 */

// 该 loader 会解析为从 Blob URL 加载的 Worker 构造函数。
// eslint-disable-next-line @typescript-eslint/no-require-imports, @typescript-eslint/no-var-requires
const RetrieveSearchWorker = require('monitor-inline-worker-loader?inline=no-fallback&esModule=false!@/storage/workers/retrieve-search.worker.ts');

export const createRetrieveSearchWorker = () => new RetrieveSearchWorker();

export const getRetrieveSearchWorkerUrl = () => 'blob:worker-loader-inline:retrieve-search.worker';
