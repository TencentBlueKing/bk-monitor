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
import {hashBytes} from './replay-capture.mjs';
import {compareSemanticNodes} from './protocol.mjs';
const baseCheckpointIds = ['query-ready', 'expanded-kv-filter', 'expanded-json', 'collapsed-restored'];

/** Recompute a limited pilot proof from artifacts; do not trust a passed boolean alone. */
export function verifyPilotBaseline(fixture, reportPath) {
  const checkpointIds = fixture.capture.context.capabilities?.includes('row-field-search-icons')
    ? ['query-ready', 'expanded-kv-filter', 'expanded-no-match', 'expanded-clear-restored', 'expanded-json', 'collapsed-restored']
    : baseCheckpointIds;
  if (fixture.capture.context.capabilities?.includes('selected-field-search-restore')) checkpointIds.splice(1,0,'sidebar-field-filter','sidebar-field-no-match','sidebar-field-restored');
  if (fixture.capture.context.capabilities?.includes('row-copy-payload-native-event')) checkpointIds.splice(checkpointIds.indexOf('collapsed-restored'),0,'expanded-copy-payload');
  const bytes = readFileSync(reportPath), report = JSON.parse(bytes);
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
  if (fixture.capture.context.capabilities?.includes('selected-field-sidebar-initial-read')) {
    const snapshots = [];
    for (const directory of [report.privateInput, report.privateDir]) {
      const path = resolve(directory, 'query-ready.sidebar.json'), body = readFileSync(path);
      artifacts.push({path, sha256: hashBytes(body), bytes: body.length});snapshots.push(JSON.parse(body));
    }
    if (!snapshots[0].fieldNames.length || JSON.stringify(snapshots[0].fieldNames) !== JSON.stringify(snapshots[1].fieldNames)) throw new Error('SIDEBAR_BASELINE_SELF_REPLAY_FAILED');
  }
  if (fixture.capture.context.capabilities?.includes('row-copy-payload-native-event')) {
    const copies = [];
    for (const directory of [report.privateInput, report.privateDir]) {
      const path = resolve(directory,'expanded-copy-payload.clipboard.json'), body = readFileSync(path);
      artifacts.push({path,sha256:hashBytes(body),bytes:body.length});copies.push(JSON.parse(body));
    }
    if (JSON.stringify(copies[0]) !== JSON.stringify(copies[1])) throw new Error('COPY_PAYLOAD_SELF_REPLAY_MISMATCH');
  }
  return {schemaVersion: 1, capabilities: fixture.capture.context.capabilities ?? ['row-expand-kv-json-restore'], scope: 'ROW_EXPAND_KV_JSON_RESTORE_ONLY', status: 'PILOT_BASELINE_PROVEN', captureDigest: fixture.captureDigest, sourceDigest: fixture.capture.sourceDigest, report: {path: reportPath, sha256: hashBytes(bytes)}, artifacts, exclusions: fixture.exclusions, fullProductAccepted: false};
}
