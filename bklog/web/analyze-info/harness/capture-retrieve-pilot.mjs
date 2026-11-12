import { bindTargetContracts } from './runtime-target.mjs';
import { localArtifactUrl, localArtifactPath } from './local-artifacts.mjs';
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
import {snapshotRetrieveContract, verifyRetrieveContract} from './contract-pin.mjs';
import {runRetrieveRowPilot} from './retrieve-row-pilot.mjs';
const require = createRequire(new URL('../../packages/web-v3/package.json', import.meta.url));
const {chromium, expect} = require('@playwright/test');
const target = process.argv[2];
if (!target || new URL(target).hostname !== 'appdev.woa.com') throw new Error('DEV_HOST_REQUIRED');
const rules = bindTargetContracts(JSON.parse(readFileSync(new URL('../spec/read-policy.json', import.meta.url), 'utf8')).rules, target);
for (const rule of rules) {
  const body = readFileSync(new URL('../../packages/web-v2/src/' + rule.source.file, import.meta.url));
  if (createHash('sha256').update(body).digest('hex') !== rule.source.sha256) throw new Error('POLICY_SOURCE_CHANGED');
}
const scenario = JSON.parse(readFileSync(localArtifactUrl('scenarios/retrieve-row-expand.json'), 'utf8'));
for (const ref of scenario.sourceRefs) {
  const bytes = readFileSync(new URL('../../packages/web-v2/src/' + ref.file, import.meta.url));
  if (createHash('sha256').update(bytes).digest('hex') !== ref.sha256) throw new Error('SCENARIO_SOURCE_CHANGED');
}
const sourceGraph = JSON.parse(readFileSync(localArtifactUrl('source/entry-graph.json'), 'utf8'));
for (const ref of sourceGraph.files) {
  const bytes = readFileSync(new URL('../../packages/web-v2/src/' + ref.file, import.meta.url));
  if (createHash('sha256').update(bytes).digest('hex') !== ref.sha256) throw new Error('INVENTORY_SOURCE_CHANGED');
}
const contractPin = snapshotRetrieveContract();
const privateDir = mkdtempSync(resolve(tmpdir(), 'bklog-v2-pilot-'));
const browser = await chromium.launch({headless: true, executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
const checkpoints = [], failures = [], runtimeErrors = [];
let recorder;
try {
  const context = await browser.newContext({viewport: {width: 1440, height: 900}, timezoneId: 'Asia/Shanghai', locale: 'zh-CN', serviceWorkers: 'block'});
  const page = await context.newPage();
  page.on('pageerror', () => runtimeErrors.push('UNCAUGHT_PAGE_ERROR'));
  page.on('console', message => {if(message.type()==='error' && message.text().startsWith('[field-filter] render failed'))runtimeErrors.push('FIELD_FILTER_RENDER_BOUNDARY_ERROR');});
  await page.clock.setFixedTime(new Date(scenario.context.clockEpochMs));
  const cdp = await context.newCDPSession(page);
  const transportRequests = [];
  cdp.on('Network.requestWillBeSent', event => transportRequests.push({id: event.requestId, url: event.request.url, method: event.request.method, body: event.request.postData ?? null}));
  await cdp.send('Network.enable', {maxTotalBufferSize: 256 * 1024 * 1024, maxResourceBufferSize: 128 * 1024 * 1024, enableDurableMessages: true});
  recorder = await installRecorder(context, {
    origin: new URL(target).origin, rules, privateDir,
    businessContext: scenario.context,
    async bodyFallback(request) {
      const candidates = transportRequests.filter(r => r.url === request.url() && r.method === request.method() && r.body === request.postData());
      const ids = [...new Set(candidates.map(r => r.id))];
      if (ids.length !== 1) throw new Error('BODY_FALLBACK_AMBIGUOUS_TRANSPORT_ID');
      const result = await cdp.send('Network.getResponseBody', {requestId: ids[0]});
      return {body: Buffer.from(result.body, result.base64Encoded ? 'base64' : 'utf8'), transport: {source: 'CDP_UNIQUE_REQUEST_ID', requestId: ids[0]}};
    },
  });
  await page.goto(target, {waitUntil: 'domcontentloaded', timeout: 60000});
  await runRetrieveRowPilot(page, {
    entries: recorder.entries, privateDir, checkpoints, expectedContext: scenario.context,
    readRequest: entry => JSON.parse(readFileSync(resolve(privateDir, entry.request.path), 'utf8')),
    readBody: entry => readFileSync(resolve(privateDir, entry.response.body.path), 'utf8'),
    setPhase: id => recorder.phase(id),
  });
} catch (error) {failures.push({reason: error.message.slice(0, 700)});}
finally {
  await recorder?.flush();
  if(runtimeErrors.length)failures.push({reason:'RUNTIME_ERRORS_OBSERVED',count:runtimeErrors.length});
  try {verifyRetrieveContract(contractPin);} catch (error) {failures.push({reason: error.message});}
  recorder?.save('capture.json', {contractPin, sourceManifest: sourceGraph.files, sourceDigest: sourceGraph.sourceDigest, scenarioId: scenario.id, scenarioRevision: scenario.revision, sourceRefs: scenario.sourceRefs, context: scenario.context});
  const out = localArtifactUrl('runs/pilot/');mkdirSync(out, {recursive: true});
  const result = {schemaVersion: 1, scope: 'V2_PILOT_CAPTURE_NOT_ACCEPTED_BASELINE', status: failures.length ? 'INVALID_RUN' : 'CAPTURED_NEEDS_SELF_REPLAY', privateDir, checkpoints, failures, requests: recorder?.publicSummary()};
  const filename = new URL(`retrieve-${Date.now()}.json`, out);
  writeFileSync(filename, JSON.stringify(result, null, 2) + '\n');
  console.log(JSON.stringify({status: result.status, details: 'PRIVATE_LOCAL_REPORT'}));
  await browser.close();
}
