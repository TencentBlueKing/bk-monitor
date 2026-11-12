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
import {readFileSync, writeFileSync, mkdirSync, mkdtempSync} from 'node:fs';
import {resolve} from 'node:path';
import {tmpdir} from 'node:os';
import {fileURLToPath} from 'node:url';
import {loadCapture, ReplaySequence} from './replay-capture.mjs';
import {compareSemanticNodes} from './protocol.mjs';
import {installReplayTransport} from './replay-transport.mjs';
import {verifyRetrieveContract} from './contract-pin.mjs';
import {runRetrieveRowPilot} from './retrieve-row-pilot.mjs';
const require = createRequire(new URL('../../packages/web-v3/package.json', import.meta.url));
const {chromium} = require('@playwright/test');
const [privateInput, target, version = 'v2', baselineReport] = process.argv.slice(2);
if (!['v2', 'v3'].includes(version)) throw new Error('TARGET_VERSION_REQUIRED');
if (!target || new URL(target).hostname !== 'appdev.woa.com') throw new Error('DEV_HOST_REQUIRED');
const rules = JSON.parse(readFileSync(new URL('../spec/read-policy.json', import.meta.url), 'utf8')).rules;
const cancelContracts = JSON.parse(readFileSync(new URL('../spec/cancel-contracts.json', import.meta.url), 'utf8')).contracts;
const sourceRoot = fileURLToPath(new URL('../../packages/web-v2/src/', import.meta.url));
const expectedSourceDigest = JSON.parse(readFileSync(new URL('../source/entry-graph.json', import.meta.url), 'utf8')).sourceDigest;
const fixture = loadCapture(privateInput, {sourceRoot, rules, cancelContracts, expectedSourceDigest});
if (fixture.capture.scenarioRevision >= 3 || fixture.capture.contractPin) verifyRetrieveContract(fixture.capture.contractPin);
let baselineProof;
if (version === 'v3') {
  const {verifyPilotBaseline} = await import('./pilot-baseline.mjs');
  baselineProof = verifyPilotBaseline(fixture, baselineReport);
}
const sequence = new ReplaySequence(fixture);
const privateDir = mkdtempSync(resolve(tmpdir(), 'bklog-v2-self-replay-'));
const browser = await chromium.launch({headless: true, executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
const entries = [], checkpoints = [], failures = [], cancellations = [], uiDifferences = [], runtimeErrors = [];
let page;
const routeDecisions = [];
try {
  const context = await browser.newContext({viewport: {width: 1440, height: 900}, timezoneId: 'Asia/Shanghai', locale: 'zh-CN', serviceWorkers: 'block'});
  const replayTransport = await installReplayTransport(context, {target, fixture, rules, sequence, entries, failures, cancellations, routeDecisions});
  page = await context.newPage();
  if (process.env.BKLOG_DEBUG_FIELDS === '1') page.on('response', async response => {
    if (new URL(response.url()).pathname.endsWith('/field-filter-comp/index.tsx')) {
      try {writeFileSync(resolve(privateDir, 'field-filter-compiled.js'), await response.text(), {mode: 0o600});} catch {}
    }
  });
  page.on('pageerror', error => runtimeErrors.push(error.message.replace(/https?:[^ ]+/g, '<url>').slice(0, 300)));
  page.on('console', message => {if(message.type()==='error' && message.text().startsWith('[field-filter] render failed')) runtimeErrors.push('FIELD_FILTER_RENDER_BOUNDARY_ERROR');});
  if (!fixture.capture.context?.clockEpochMs) throw new Error('CAPTURE_CLOCK_NOT_FIXED');
  await page.clock.setFixedTime(new Date(fixture.capture.context.clockEpochMs));
  await page.goto(target, {waitUntil: 'domcontentloaded', timeout: 60000});
  await runRetrieveRowPilot(page, {entries, privateDir, checkpoints, setPhase: id => replayTransport.phase(id), expectedContext: fixture.capture.context, readRequest: entry => entry.fixtureRecord.requestData, readBody: entry => entry.fixtureRecord.body.toString('utf8')});
  sequence.assertConsumed();
  if (fixture.capture.contractPin) verifyRetrieveContract(fixture.capture.contractPin);
  for (const checkpoint of checkpoints) {
    const expected = JSON.parse(readFileSync(resolve(privateInput, checkpoint.id + '.ui.json'), 'utf8'));
    const actual = JSON.parse(readFileSync(resolve(privateDir, checkpoint.id + '.ui.json'), 'utf8'));
    uiDifferences.push(...compareSemanticNodes(expected.nodes, actual.nodes, {geometryTolerance: 1}).map(diff => ({checkpoint: checkpoint.id, ...diff})));
  }
  if (fixture.capture.context.capabilities?.includes('selected-field-sidebar-initial-read')) {
    const expected = JSON.parse(readFileSync(resolve(privateInput, 'query-ready.sidebar.json'), 'utf8'));
    const actual = JSON.parse(readFileSync(resolve(privateDir, 'query-ready.sidebar.json'), 'utf8'));
    if (!expected.fieldNames.length) throw new Error('SIDEBAR_BASELINE_EMPTY');
    if (JSON.stringify(expected.fieldNames) !== JSON.stringify(actual.fieldNames)) uiDifferences.push({checkpoint: 'query-ready', kind: 'FIELD_ORDER', id: 'retrieval.selected-fields', expected: expected.fieldNames, actual: actual.fieldNames});
  }
  if (fixture.capture.context.capabilities?.includes('row-copy-payload-native-event')) {
    const expected = JSON.parse(readFileSync(resolve(privateInput,'expanded-copy-payload.clipboard.json')));
    const actual = JSON.parse(readFileSync(resolve(privateDir,'expanded-copy-payload.clipboard.json')));
    if (JSON.stringify(expected) !== JSON.stringify(actual)) failures.push({reason:'COPY_PAYLOAD_DIFFERS_FROM_V2'});
  }
  if (uiDifferences.length) failures.push({reason: 'SELF_REPLAY_UI_DIFFERENCE', count: uiDifferences.length});
} catch (error) {failures.push({reason: error.message.slice(0, 700)});await page?.screenshot({path: resolve(privateDir, 'failure.png')}).catch(() => {});}
finally {
  await browser.close();
  if(runtimeErrors.length) failures.push({reason:'RUNTIME_ERRORS_OBSERVED',count:runtimeErrors.length});
  const result = {schemaVersion: 1, scope: 'SINGLE_ROW_PILOT_ONLY_NOT_FULL_V2_V3_ACCEPTANCE', version, oraclePin: fixture.capture.contractPin?.digest ?? 'LEGACY_UNPINNED_SCOPE_ONLY', status: failures.length ? (version === 'v2' ? 'INVALID_SELF_REPLAY' : 'V3_PILOT_REQUIRES_REVIEW') : (version === 'v2' ? 'PILOT_SELF_REPLAY_PASSED' : 'V3_PILOT_ORACLES_PASSED'), baselineProof, runtimeErrors, captureDigest: fixture.captureDigest, privateInput, privateDir, fixtureReadRecords: fixture.records.length, consumedRecords: sequence.used.size, businessRequestsForwarded: routeDecisions.filter(e => e.action === 'FORWARD' && e.kind === 'BUSINESS').length, networkAudit: {scope: 'CONTEXT_ROUTE_HANDLER_AUDIT', interceptedBusiness: routeDecisions.filter(e => e.kind === 'BUSINESS').length, forwardedStatic: routeDecisions.filter(e => e.kind === 'STATIC').length}, checkpoints, cancellations, uiDifferences, failures};
  const dir = new URL('../runs/pilot/', import.meta.url);mkdirSync(dir, {recursive: true});
  writeFileSync(new URL(`${version === 'v2' ? 'self-replay' : 'v3-compare'}-${Date.now()}.json`, dir), JSON.stringify(result, null, 2) + '\n');
  console.log(JSON.stringify({...result, baselineProof: baselineProof && {status: baselineProof.status, scope: baselineProof.scope, captureDigest: baselineProof.captureDigest}, checkpoints: checkpoints.map(c => c.id), uiDifferences: undefined}));
  if (failures.length) process.exitCode = 1;
}
