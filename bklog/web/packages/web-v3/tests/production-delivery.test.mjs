/* Copyright (C) 2021 THL A29 Limited, a Tencent company, MIT License. */
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, mkdtempSync, mkdirSync, writeFileSync, rmSync, chmodSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { spawnSync } from 'node:child_process';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { productionOutput } from '../tools/production-paths.mjs';
import { productionHtml, environmentTemplate } from '../tools/production-delivery.mjs';
import { verifyProductionBuild } from '../tools/verify-production-build.mjs';

test('production directory and backend runtime template preserve the V2 server contract', () => {
  assert.equal(productionOutput, fileURLToPath(new URL('../../../../static/dist/', import.meta.url)));
  const v2 = readFileSync(new URL('../../web-v2/webpack.config.js', import.meta.url), 'utf8');
  const variables = v2.split('pcBuildVariates: `')[1].split('`,\n};')[0].replaceAll('\\${', '${').trim();
  assert.equal(environmentTemplate.trim(), variables);
  const make = readFileSync(new URL('../../../../Makefile', import.meta.url), 'utf8');
  assert.match(make, /cd web && node scripts\/build-web.mjs/);
  assert.doesNotMatch(make, /npm install --legacy-peer-deps/);
});
test('HTML uses backend static prefix and preserves the module script bootstrap ordering', () => {
  const html = productionHtml('<head><title>Dev</title><script type="module" src="./assets/app.js"></script><link href="./assets/app.css"></head>');
  assert.match(html, /src="\$\{BK_STATIC_URL\}\/assets\/app.js"/);
  assert.match(html, /href="\$\{BK_STATIC_URL\}\/assets\/app.css"/);
  assert.ok(html.includes('${TITLE}'));
  assert.ok(html.includes('window.AJAX_URL_PREFIX'));
  assert.ok(html.includes('window.BKLOG_RUM'));
});
test('production artifact checks reject missing resources and origin-root asset URLs', t => {
  const dir = mkdtempSync(join(tmpdir(), 'bklog-production-synthetic-'));
  t.after(() => rmSync(dir, { recursive: true, force: true }));
  mkdirSync(join(dir, 'assets'));
  writeFileSync(join(dir, 'index.html'), productionHtml('<head><title>x</title><script type="module" src="./assets/app.js"></script><link href="./assets/app.css"></head>'));
  writeFileSync(join(dir, 'assets/app.js'), 'export const synthetic = true;');
  writeFileSync(join(dir, 'assets/app.css'), 'body { color: red; }');
  writeFileSync(join(dir, 'asset-manifest.js'), 'self.assetData =["__STATIC_URL__assets/app.js","__STATIC_URL__assets/app.css"];');
  assert.equal(verifyProductionBuild(dir).status, 'PRODUCTION_DELIVERY_VERIFIED');
  writeFileSync(join(dir, '.env.local'), 'SYNTHETIC_ONLY=true');
  assert.throws(() => verifyProductionBuild(dir), /Private/);
  rmSync(join(dir, '.env.local'));
  writeFileSync(join(dir, 'assets/raw-worker.ts'), 'export type Synthetic = string;');
  assert.throws(() => verifyProductionBuild(dir), /Private/);
  rmSync(join(dir, 'assets/raw-worker.ts'));
  rmSync(join(dir, 'assets/app.css'));
  assert.throws(() => verifyProductionBuild(dir), /Missing/);
});

test('Make installer works on npm-only hosts and isolates both commands to the Vue3 package', t => {
  const dir = mkdtempSync(join(tmpdir(), 'bklog-build-bootstrap-synthetic-'));
  t.after(() => rmSync(dir, { recursive: true, force: true }));
  const trace = join(dir, 'trace.txt'), shim = join(dir, 'npx');
  writeFileSync(shim, `#!/bin/sh\nprintf '%s\\n' "$PWD|$NODE_ENV|$*" >> "$SYNTHETIC_TRACE"\n`);
  chmodSync(shim, 0o755);
  const result = spawnSync(process.execPath, [fileURLToPath(new URL('../../../scripts/build-web.mjs', import.meta.url))], {
    env: { ...process.env, PATH: dir, PNPM: '', NODE_ENV: 'development', SYNTHETIC_TRACE: trace }, encoding: 'utf8',
  });
  assert.equal(result.status, 0, result.stderr);
  const lines = readFileSync(trace, 'utf8').trim().split('\n');
  assert.equal(lines.length, 2);
  assert.ok(lines.every(line => line.includes('/packages/web-v3|') && line.includes('|--yes pnpm@')));
  assert.match(lines[0], /--ignore-workspace install --frozen-lockfile --prod=false$/);
  assert.match(lines[1], /\|production\|--yes pnpm@/);
  assert.match(lines[1], /--ignore-workspace run build$/);
});
