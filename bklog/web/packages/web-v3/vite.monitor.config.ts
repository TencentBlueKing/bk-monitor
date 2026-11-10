/* Copyright (C) 2021 THL A29 Limited, a Tencent company.
 * 蓝鲸智云PaaS平台 (BlueKing PaaS), MIT License. */
import { fileURLToPath } from 'node:url';
import { resolve } from 'node:path';
import application from './vite.application.config.mjs';
import { monitorControlStyleScope } from './tools/monitor-style-scope.mjs';
import { monitorBuildIdentity } from './tools/verify-monitor-build.mjs';
const here = fileURLToPath(new URL('.', import.meta.url));
const kind = process.env.MONITOR_APP;
let monitorIdentity: string;
if (kind !== 'apm' && kind !== 'trace') throw new Error('Monitor build requires MONITOR_APP=apm or trace');

// Build into an isolated directory until host integration has passed. The old
// published package is never overwritten as a side effect of local verification.
export default {
  ...application,
  publicDir: false,
  base: './',
  plugins: [...application.plugins, {
    name: 'monitor-build-source-stability',
    apply: 'build',
    buildStart() { monitorIdentity = JSON.stringify(monitorBuildIdentity()); },
    generateBundle() {
      if (monitorIdentity !== JSON.stringify(monitorBuildIdentity())) this.error('Sources changed during Monitor build; rebuild a stable snapshot');
      this.emitFile({ type: 'asset', fileName: 'build-identity.json', source: monitorIdentity });
    },
  }],
  css: { ...application.css, postcss: { plugins: [monitorControlStyleScope(kind)] } },
  experimental: {
    renderBuiltUrl(filename: string, context: { hostType: string }) {
      if (context.hostType === 'js')
        return {
          runtime: `new URL(${JSON.stringify(filename)}, new URL(String(window.BK_STATIC_URL || './').replace(/\\/?$/, '/'), document.baseURI)).href`,
        };
      return { relative: true };
    },
  },
  build: {
    ...application.build,
    outDir: resolve(here, `dist-monitor/${kind}`),
    cssCodeSplit: false,
    assetsInlineLimit: 0,
    rollupOptions: {
      preserveEntrySignatures: 'strict',
      input: resolve(here, `src/app/entries/${kind}.ts`),
      output: {
        format: 'cjs',
        exports: 'named',
        inlineDynamicImports: true,
        entryFileNames: 'main.js',
        assetFileNames: (asset: { names: string[] }) =>
          asset.names.some(name => name.endsWith('.css')) ? 'css/main.css' : 'assets/[name]-[hash][extname]',
      },
    },
  },
};
