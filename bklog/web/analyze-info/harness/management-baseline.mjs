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

import {readFileSync} from 'node:fs';
import {resolve} from 'node:path';
import {verifyManagementContract} from './management-contract-pin.mjs';
import {hashBytes} from './replay-capture.mjs';
import {compareSemanticNodes} from './protocol.mjs';
const menuCheckpointIds = ['list-ready', 'menu-open', 'stop-type-preview', 'cancel-restored-list'];

/** Recompute a limited pilot proof from artifacts; do not trust a passed boolean alone. */
export function verifyManagementBaseline(fixture, reportPath) {
  const checkpointIds = [...menuCheckpointIds, ...(fixture.capture.pilotMode === 'navigation' ? ['collapsed-nav-ready', 'nav-cluster-ready'] : []), ...(fixture.capture.pilotMode?.startsWith('labels') ? ['label-popup-preview', 'label-filter-no-match', 'label-required-validation', fixture.capture.pilotMode === 'labels-cancel' ? 'label-cancel-restored' : 'label-close-restored'] : [])];
  if (fixture.capture.clusterSearchPreview) checkpointIds.push('cluster-search-empty', 'cluster-search-restored');
  const bytes = readFileSync(reportPath), report = JSON.parse(bytes);
  if (!Array.isArray(report.runtimeErrors) || report.runtimeErrors.length) throw new Error('PILOT_RUNTIME_ERRORS_NOT_CLEAN');
  verifyManagementContract(fixture.capture.contractPin, fixture.capture.scenarioId);
  if (report.oraclePin !== fixture.capture.contractPin.digest) throw new Error('PILOT_ORACLE_PIN_MISMATCH');
  if (report.status !== 'PILOT_SELF_REPLAY_PASSED' || report.captureDigest !== fixture.captureDigest || report.failures.length || report.consumedRecords !== fixture.records.length || report.fixtureReadRecords !== fixture.records.length || report.businessRequestsForwarded !== 0) throw new Error('PILOT_SELF_REPLAY_NOT_PROVEN');
  if (JSON.stringify(report.checkpoints.map(c => c.id)) !== JSON.stringify(checkpointIds)) throw new Error('PILOT_CHECKPOINTS_INCOMPLETE');
  const cancelled = fixture.records.filter(e => e.kind === 'EXPECTED_CLIENT_CANCEL');
  if (cancelled.some(e => report.cancellations.filter(c => c.id === e.id && c.clientCancellationObserved === true).length !== 1)) throw new Error('PILOT_CANCEL_NOT_PROVEN');
  const artifacts = [];
  for (const id of checkpointIds) {
    const nodes = [];
    for (const directory of [report.privateInput, report.privateDir]) {
      for (const extension of ['ui.json', 'png']) {
        const path = resolve(directory, id + '.' + extension), body = readFileSync(path);
        artifacts.push({path, sha256: hashBytes(body), bytes: body.length});
        if (extension === 'ui.json') {
          const snapshot = JSON.parse(body);
          if (snapshot.errors.length || snapshot.viewport.width !== 1440 || snapshot.viewport.height !== 900) throw new Error('PILOT_UI_ARTIFACT_INVALID');
          nodes.push(snapshot.nodes);
        }
      }
    }
    if (compareSemanticNodes(nodes[0], nodes[1], {geometryTolerance: 1}).length) throw new Error('PILOT_SELF_UI_NOT_EQUIVALENT');
  }
  return {schemaVersion: 1, capabilities: ['management-menu-stop-preview-cancel'], scope: 'MANAGEMENT_MENU_PREVIEW_CANCEL_ONLY', status: 'PILOT_BASELINE_PROVEN', captureDigest: fixture.captureDigest, sourceDigest: fixture.capture.sourceDigest, report: {path: reportPath, sha256: hashBytes(bytes)}, artifacts, exclusions: fixture.exclusions, fullProductAccepted: false};
}
