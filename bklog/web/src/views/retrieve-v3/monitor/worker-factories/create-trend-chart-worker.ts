/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * 仅用于 Monitor 嵌入构建：将趋势图 Worker 内联为 Blob。
 *
 * monitor-inline-worker-loader 是 worker-loader 的包装，由 scripts/create-monitor.js
 * 通过 resolveLoader.alias 注入，作用是让 Worker 子编译不继承本构建的 commonjs externals。
 */

// eslint-disable-next-line @typescript-eslint/no-require-imports, @typescript-eslint/no-var-requires
const TrendChartWorker = require('monitor-inline-worker-loader?inline=no-fallback&esModule=false!@/hooks/workers/trend-chart-worker.ts');

export const createTrendChartWorker = () => new TrendChartWorker();
