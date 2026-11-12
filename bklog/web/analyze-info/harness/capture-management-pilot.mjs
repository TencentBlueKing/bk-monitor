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

import {createRequire} from 'node:module';
import {readFileSync, writeFileSync, mkdtempSync, mkdirSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {resolve} from 'node:path';
import {createHash} from 'node:crypto';
import {installRecorder} from './network-recorder.mjs';
import {createCaptureTransport} from './capture-transport.mjs';
import {snapshotManagementContract, verifyManagementContract} from './management-contract-pin.mjs';
import {runManagementMenuPilot} from './management-menu-pilot.mjs';
const require = createRequire(new URL('../../packages/web-v3/package.json', import.meta.url));
const {chromium} = require('@playwright/test');
const target = process.argv[2];
if (!target || new URL(target).hostname !== 'appdev.woa.com') throw new Error('DEV_HOST_REQUIRED');
const scenario = JSON.parse(readFileSync(new URL(process.env.BKLOG_NAV_CLUSTER_PREVIEW === '1' ? '../scenarios/management-nav-cluster-read.json' : '../scenarios/management-menu-cancel.json', import.meta.url), 'utf8'));
const graph = JSON.parse(readFileSync(new URL('../source/entry-graph.json', import.meta.url), 'utf8'));
const rules = JSON.parse(readFileSync(new URL('../spec/read-policy.json', import.meta.url), 'utf8')).rules;
for (const ref of [...graph.files, ...scenario.sourceRefs, ...rules.map(rule => rule.source)]) {
  const body = readFileSync(new URL('../../packages/web-v2/src/' + ref.file, import.meta.url));
  if (createHash('sha256').update(body).digest('hex') !== ref.sha256) throw new Error('CAPTURE_SOURCE_CHANGED');
}
const contractPin = snapshotManagementContract(scenario.id);
const privateDir = mkdtempSync(resolve(tmpdir(), 'bklog-v2-management-'));
const browser = await chromium.launch({headless: true, executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
const checkpoints = [], failures = [], runtimeErrors = [];
let recorder, page;
try {
  const context = await browser.newContext({viewport: scenario.context.viewport, timezoneId: scenario.context.timezone, locale: scenario.context.locale, serviceWorkers: 'block'});
  const transport = await createCaptureTransport(context, scenario.context.clockEpochMs);page = transport.page;
  page.on('pageerror', error => runtimeErrors.push(error.message.replace(/https?:[^ ]+/g, '<url>').slice(0, 300)));
  recorder = await installRecorder(context, {origin: new URL(target).origin, rules, privateDir, businessContext: {spaceUid: 'bkcc__5000140', bizId: '5000140'}, bodyFallback: transport.bodyFallback});
  await page.goto(target, {waitUntil: 'domcontentloaded', timeout: 60000});
  await runManagementMenuPilot(page, {entries: recorder.entries, privateDir, checkpoints, readBody: entry => readFileSync(resolve(privateDir, entry.response.body.path), 'utf8'), readRequest: entry => JSON.parse(readFileSync(resolve(privateDir, entry.request.path), 'utf8')), setPhase: id => recorder.phase(id), labelPreview: process.env.BKLOG_LABEL_PREVIEW === '1', labelCancelPreview: process.env.BKLOG_LABEL_CANCEL_PREVIEW === '1', clusterSearchPreview: process.env.BKLOG_CLUSTER_SEARCH_PREVIEW === '1', navClusterPreview: process.env.BKLOG_NAV_CLUSTER_PREVIEW === '1'});
} catch (error) {
  failures.push({reason: error.message.slice(0, 700)});
  await page?.screenshot({path: resolve(privateDir, 'failure.png')}).catch(() => {});
} finally {
  await recorder?.flush();
  try {verifyManagementContract(contractPin, scenario.id);} catch (error) {failures.push({reason: error.message});}
  if (runtimeErrors.length) failures.push({reason: 'UNCAUGHT_RUNTIME_ERRORS', count: runtimeErrors.length});
  recorder?.save('capture.json', {contractPin, clusterSearchPreview: process.env.BKLOG_CLUSTER_SEARCH_PREVIEW === '1', pilotMode: process.env.BKLOG_NAV_CLUSTER_PREVIEW === '1' ? 'navigation' : process.env.BKLOG_LABEL_CANCEL_PREVIEW === '1' ? 'labels-cancel' : process.env.BKLOG_LABEL_PREVIEW === '1' ? 'labels' : 'menu', scenarioId: scenario.id, scenarioRevision: scenario.revision, sourceRefs: scenario.sourceRefs, sourceManifest: graph.files, sourceDigest: graph.sourceDigest, context: scenario.context});
  await browser.close();
  const out = new URL('../runs/pilot/', import.meta.url);mkdirSync(out, {recursive: true});
  const result = {schemaVersion: 1, scope: 'MANAGEMENT_PREVIEW_CANCEL_NO_RESOURCE_MUTATION', status: failures.length ? 'INVALID_RUN' : 'CAPTURED_NEEDS_SELF_REPLAY', privateDir, checkpoints, failures, runtimeErrors, oraclePin: contractPin.digest, requests: recorder?.publicSummary()};
  writeFileSync(new URL(`management-${Date.now()}.json`, out), JSON.stringify(result, null, 2) + '\n');
  console.log(JSON.stringify({...result, requests: recorder?.entries.length, checkpoints: checkpoints.map(c => c.id)}));
  if (failures.length) process.exitCode = 1;
}
