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
import {readFileSync, writeFileSync, mkdirSync, mkdtempSync} from 'node:fs';
import {resolve} from 'node:path';
import {tmpdir} from 'node:os';
import {fileURLToPath} from 'node:url';
import {loadCapture, ReplaySequence} from './replay-capture.mjs';
import {compareSemanticNodes} from './protocol.mjs';
import {installReplayTransport} from './replay-transport.mjs';
import {verifyManagementContract} from './management-contract-pin.mjs';
import {runManagementMenuPilot} from './management-menu-pilot.mjs';
const require = createRequire(new URL('../../packages/web-v3/package.json', import.meta.url));
const {chromium} = require('@playwright/test');
const [privateInput, target, version = 'v2', baselineReport] = process.argv.slice(2);
if (!['v2', 'v3'].includes(version)) throw new Error('TARGET_VERSION_REQUIRED');
if (!target || new URL(target).hostname !== 'appdev.woa.com') throw new Error('DEV_HOST_REQUIRED');
const rules = bindTargetContracts(JSON.parse(readFileSync(new URL('../spec/read-policy.json', import.meta.url), 'utf8')).rules, target);
const cancelContracts = bindTargetContracts(JSON.parse(readFileSync(new URL('../spec/cancel-contracts.json', import.meta.url), 'utf8')).contracts, target);
const sourceRoot = fileURLToPath(new URL('../../packages/web-v2/src/', import.meta.url));
const expectedSourceDigest = JSON.parse(readFileSync(localArtifactUrl('source/entry-graph.json'), 'utf8')).sourceDigest;
const sequenceContracts = JSON.parse(readFileSync(new URL('../spec/sequence-contracts.json', import.meta.url), 'utf8')).contracts;
const fixture = loadCapture(privateInput, {sourceRoot, rules, cancelContracts, expectedSourceDigest, sequenceContracts});
verifyManagementContract(fixture.capture.contractPin, fixture.capture.scenarioId);
let baselineProof;
if (version === 'v3') {
  const {verifyManagementBaseline} = await import('./management-baseline.mjs');
  baselineProof = verifyManagementBaseline(fixture, baselineReport);
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
  page.on('pageerror', error => runtimeErrors.push(error.message.replace(/https?:[^ ]+/g, '<url>').slice(0, 300)));
  if (!fixture.capture.context?.clockEpochMs) throw new Error('CAPTURE_CLOCK_NOT_FIXED');
  await page.clock.setFixedTime(new Date(fixture.capture.context.clockEpochMs));
  await page.goto(target, {waitUntil: 'domcontentloaded', timeout: 60000});
  await runManagementMenuPilot(page, {entries, privateDir, checkpoints, expectedContext: fixture.capture.context, setPhase: id => replayTransport.phase(id), readBody: entry => entry.fixtureRecord.body.toString('utf8'), readRequest: entry => entry.fixtureRecord.requestData, labelPreview: fixture.capture.pilotMode?.startsWith('labels'), labelCancelPreview: fixture.capture.pilotMode === 'labels-cancel', clusterSearchPreview: fixture.capture.clusterSearchPreview === true, navClusterPreview: fixture.capture.pilotMode === 'navigation'});
  verifyManagementContract(fixture.capture.contractPin, fixture.capture.scenarioId);
  sequence.assertConsumed();
  for (const checkpoint of checkpoints) {
    const expected = JSON.parse(readFileSync(resolve(privateInput, checkpoint.id + '.ui.json'), 'utf8'));
    const actual = JSON.parse(readFileSync(resolve(privateDir, checkpoint.id + '.ui.json'), 'utf8'));
    uiDifferences.push(...compareSemanticNodes(expected.nodes, actual.nodes, {geometryTolerance: 1}).map(diff => ({checkpoint: checkpoint.id, ...diff})));
  }
  const expectedMenu = JSON.parse(readFileSync(resolve(privateInput, 'menu-items.json'), 'utf8'));
  const actualMenu = JSON.parse(readFileSync(resolve(privateDir, 'menu-items.json'), 'utf8'));
  if (JSON.stringify(expectedMenu) !== JSON.stringify(actualMenu)) uiDifferences.push({kind: 'MENU_CONTENT', expected: expectedMenu, actual: actualMenu});
  if (uiDifferences.length) failures.push({reason: 'SELF_REPLAY_UI_DIFFERENCE', count: uiDifferences.length});
} catch (error) {failures.push({reason: error.message.slice(0, 700)});await page?.screenshot({path: resolve(privateDir, 'failure.png')}).catch(() => {});}
finally {
  await browser.close();
  if (runtimeErrors.length) failures.push({reason: 'UNCAUGHT_RUNTIME_ERRORS', count: runtimeErrors.length});
  const result = {schemaVersion: 1, scope: fixture.capture.pilotMode === 'navigation' ? 'MANAGEMENT_COLLAPSED_NAV_CLUSTER_READ_ONLY_NOT_FULL_ACCEPTANCE' : fixture.capture.pilotMode?.startsWith('labels') ? 'MANAGEMENT_MENU_AND_LABEL_READONLY_PREVIEW_NOT_FULL_ACCEPTANCE' : 'MANAGEMENT_MENU_PREVIEW_CANCEL_ONLY_NOT_FULL_ACCEPTANCE', version, oraclePin: fixture.capture.contractPin.digest, status: failures.length ? (version === 'v2' ? 'INVALID_SELF_REPLAY' : 'V3_PILOT_REQUIRES_REVIEW') : (version === 'v2' ? 'PILOT_SELF_REPLAY_PASSED' : 'V3_PILOT_ORACLES_PASSED'), baselineProof, runtimeErrors, captureDigest: fixture.captureDigest, privateInput, privateDir, fixtureReadRecords: fixture.records.length, consumedRecords: sequence.used.size, businessRequestsForwarded: routeDecisions.filter(e => e.action === 'FORWARD' && e.kind === 'BUSINESS').length, networkAudit: {scope: 'CONTEXT_ROUTE_HANDLER_AUDIT', interceptedBusiness: routeDecisions.filter(e => e.kind === 'BUSINESS').length, forwardedStatic: routeDecisions.filter(e => e.kind === 'STATIC').length}, checkpoints, cancellations, uiDifferences, failures};
  const dir = localArtifactUrl('runs/pilot/');mkdirSync(dir, {recursive: true});
  writeFileSync(new URL(`${version === 'v2' ? 'management-self-replay' : 'management-v3-compare'}-${Date.now()}.json`, dir), JSON.stringify(result, null, 2) + '\n');
  console.log(JSON.stringify({status: result.status, details: 'PRIVATE_LOCAL_REPORT'}));
  if (failures.length) process.exitCode = 1;
}
