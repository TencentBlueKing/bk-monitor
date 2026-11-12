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

import { readFileSync, mkdirSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { resolve } from 'node:path';
import { randomUUID } from 'node:crypto';
import { normalizeChange, selectGroups, verifyManifest, snapshot, runGroups, hashFile } from './regression-baseline.mjs';

const root = fileURLToPath(new URL('../', import.meta.url));
const web = resolve(root, '..');
const manifest = JSON.parse(readFileSync(resolve(root, 'baselines/ui-alignment/2026-11-12-r1/manifest.json')));
const args = process.argv.slice(2);
const changes = [];
let mode = 'run';
try {
  for (let i = 0; i < args.length; i++) {
    const arg = args[i];
    if (arg === '--verify' || arg === '--list') mode = arg.slice(2);
    else if (arg === '--all') continue;
    else if (arg === '--changed') changes.push(normalizeChange(web, args[++i] ?? ''));
    else if (arg.startsWith('--changed=')) changes.push(normalizeChange(web, arg.slice(10)));
    else throw Error(`Unknown argument: ${arg}`);
  }
  const verified = verifyManifest(manifest, web, root);
  const selection = selectGroups(manifest, changes);
  const tests = mode === 'run' && !selection.unmapped.length ? runGroups(selection.groups, web) : [];
  const after = snapshot(manifest, web);
  const changedDuringRun = after.filter((item, index) => item.sha256 !== verified.source[index].sha256);
  const status = selection.unmapped.length ? 'UNMAPPED_CHANGES' : changedDuringRun.length ? 'SOURCE_CHANGED_DURING_RUN'
    : mode === 'run' ? tests.length && tests.every(t => t.valid) ? 'SOURCE_REGRESSION_PASSED' : 'SOURCE_REGRESSION_FAILED'
    : 'REFERENCE_VERIFIED';
  const report = {
    schemaVersion: 1, baselineId: manifest.id, generatedAt: new Date().toISOString(), mode, status, changes,
    runtime: process.version,
    toolDigests: ['harness/run-regression-baseline.mjs', 'harness/regression-baseline.mjs',
      'baselines/ui-alignment/2026-11-12-r1/manifest.json'].map(path => ({ path, sha256: hashFile(resolve(root, path)) })),
    selectedGroups: selection.groups.map(g => ({ id: g.id, cases: g.tests.reduce((sum, t) => sum + t.requiredCases.length, 0) })),
    unmapped: selection.unmapped, required: tests.reduce((sum, t) => sum + t.required, 0),
    passed: tests.reduce((sum, t) => sum + t.passed, 0), tests,
    evidence: verified.evidence, source: after, changedDuringRun,
    staleReferenceFiles: after.filter(s => s.changedFromReference).map(s => s.file),
    businessAccepted: false, visualAccepted: false, uiReviewRequired: true,
    supplementalBrowserProfiles: [
      'node analyze-info/harness/native-model-regression.mjs http://appdev.woa.com:<verified-v3-port>',
      'node analyze-info/harness/collection-label-regression.mjs http://appdev.woa.com:<verified-v3-port>',
      'Retrieve / management: see 回归使用指南.md; fresh private capture and V2 self-replay required.',
    ],
  };
  const dir = resolve(root, 'runs/regression');
  mkdirSync(dir, { recursive: true });
  const output = resolve(dir, `${Date.now()}-${randomUUID().slice(0, 8)}.json`);
  writeFileSync(output, `${JSON.stringify(report, null, 2)}\n`);
  console.log(JSON.stringify({ ...report, tests: undefined, source: undefined, evidence: undefined, report: output }, null, 2));
  if (selection.unmapped.length) process.exitCode = 2;
  else if (status.endsWith('FAILED') || changedDuringRun.length) process.exitCode = 1;
} catch (error) {
  console.error(`INVALID_BASELINE: ${error.message}`);
  process.exitCode = 1;
}
