/* Copyright (C) 2021 THL A29 Limited, a Tencent company, MIT License. */
import { gzipSync } from 'node:zlib';
import { writeFileSync, mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { resolve, join } from 'node:path';
import { fileURLToPath } from 'node:url';

export function summarizeChunks(chunks, roots) {
  const byFile = new Map(chunks.map(chunk => [chunk.file, chunk]));
  const files = new Set();
  const visit = file => {
    if (files.has(file) || !byFile.has(file)) return;
    files.add(file);
    byFile.get(file).imports.forEach(visit);
  };
  roots.forEach(visit);
  return { files: [...files].sort(), bytes: [...files].reduce((sum, file) => sum + byFile.get(file).bytes, 0),
    gzip: [...files].reduce((sum, file) => sum + byFile.get(file).gzip, 0) };
}

async function main() {
  process.env.NODE_ENV = 'production';
  const root = fileURLToPath(new URL('../', import.meta.url));
  const output = process.argv[2] ? resolve(process.argv[2]) : join(mkdtempSync(join(tmpdir(), 'bklog-bundle-')), 'report.json');
  const { build } = await import('vite');
  await build({ configFile: resolve(root, 'vite.application.config.mjs'), plugins: [{
    name: 'bklog-local-bundle-report',
    generateBundle(_, bundle) {
      const chunks = Object.values(bundle).filter(item => item.type === 'chunk').map(chunk => ({
        file: chunk.fileName, entry: chunk.isEntry, imports: chunk.imports, dynamicImports: chunk.dynamicImports,
        bytes: Buffer.byteLength(chunk.code), gzip: gzipSync(chunk.code).length,
        modules: Object.entries(chunk.modules).map(([id, value]) => ({ id: id.replace(root, ''), bytes: value.renderedLength })),
      }));
      const entry = chunks.filter(chunk => chunk.entry).map(chunk => chunk.file);
      const owners = suffix => chunks.filter(chunk => chunk.modules.some(module => module.id.split('?')[0].endsWith(suffix))).map(chunk => chunk.file);
      const retrieval = owners('/features/retrieval/retrieve-hub.tsx');
      const trend = owners('/shared/composables/use-trend-chart.ts');
      const rum = chunks.filter(chunk => chunk.modules.some(module => module.id.includes('/@blueking/open-telemetry/'))).map(chunk => chunk.file);
      const scenarios = {
        entry: summarizeChunks(chunks, entry),
        entryWithRum: summarizeChunks(chunks, [...entry, ...rum]),
        retrieval: summarizeChunks(chunks, [...entry, ...retrieval]),
        retrievalWithTrend: summarizeChunks(chunks, [...entry, ...retrieval, ...trend]),
        retrievalWithTrendWithRum: summarizeChunks(chunks, [...entry, ...retrieval, ...trend, ...rum]),
      };
      // Static source/build statistics only. Never read runtime API data or cookies.
      writeFileSync(output, JSON.stringify({ scope: 'JavaScript static dependency closures; excludes CSS, API and interaction-triggered imports',
        scenarios, chunks: chunks.map(chunk => ({ ...chunk, modules: chunk.modules.sort((a, b) => b.bytes - a.bytes).slice(0, 15) })) }, null, 2));
      console.log('[bundle-analysis]', JSON.stringify(scenarios));
    },
  }] });
  console.log('[bundle-analysis] Report:', output);
}
if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) await main();
