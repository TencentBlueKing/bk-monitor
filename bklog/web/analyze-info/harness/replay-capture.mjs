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

import {readFileSync, realpathSync, statSync} from 'node:fs';
import {resolve, sep} from 'node:path';
import {createHash} from 'node:crypto';
import {requestSignature, requestPolicy, parseStream} from './protocol.mjs';
export const hashBytes = value => createHash('sha256').update(value).digest('hex');

export function loadCapture(privateDir, {sourceRoot, rules, cancelContracts, expectedSourceDigest, sequenceContracts = []}) {
  const root = realpathSync(privateDir);
  if (statSync(root).mode & 0o077) throw new Error('FIXTURE_DIRECTORY_NOT_PRIVATE');
  const readArtifact = ref => {
    const path = realpathSync(resolve(root, ref.path));
    if (!path.startsWith(root + sep)) throw new Error('ARTIFACT_OUTSIDE_CAPTURE');
    const bytes = readFileSync(path);
    if (hashBytes(bytes) !== ref.sha256 || bytes.length !== ref.bytes) throw new Error('ARTIFACT_INTEGRITY_MISMATCH');
    return bytes;
  };
  const captureBytes = readFileSync(resolve(root, 'capture.json'));
  const capture = JSON.parse(captureBytes);
  if (capture.schemaVersion !== 1 || !capture.scenarioId || !capture.entries?.length || !capture.sourceManifest?.length) throw new Error('CAPTURE_SCHEMA_INCOMPLETE');
  if (!expectedSourceDigest || capture.sourceDigest !== expectedSourceDigest || hashBytes(JSON.stringify(capture.sourceManifest)) !== expectedSourceDigest) throw new Error('CAPTURE_SOURCE_MANIFEST_MISMATCH');
  for (const ref of [...capture.sourceManifest, ...rules.map(rule => rule.source), ...cancelContracts.map(c => c.source), ...sequenceContracts.map(c => c.source)]) {
    if (hashBytes(readFileSync(resolve(sourceRoot, ref.file))) !== ref.sha256) throw new Error('CAPTURE_SOURCE_CHANGED');
  }
  const records = [], exclusions = [];
  for (const entry of capture.entries) {
    if (typeof entry.observedDuring !== 'string' || !entry.observedDuring) throw new Error('CAPTURE_PHASE_MISSING');
    const request = JSON.parse(readArtifact(entry.request));
    if (requestSignature(request) !== entry.signature) throw new Error('REQUEST_SIGNATURE_TAMPERED');
    const policy = requestPolicy(request, rules);
    if (policy.ruleId !== entry.policy.ruleId || policy.decision !== entry.policy.decision) throw new Error('POLICY_EVIDENCE_CHANGED');
    if (policy.decision === 'BLOCK') {
      if (policy.reason !== 'WRITE_NOT_AUTHORIZED') throw new Error('UNREVIEWED_REQUEST_IN_CAPTURE');
      exclusions.push({path: entry.path, method: entry.method, ruleId: policy.ruleId});
      continue;
    }
    if (entry.complete === true && entry.response?.body) {
      const body = readArtifact(entry.response.body);
      if (/ndjson/i.test(entry.response.contentType)) {
        if (!parseStream(body.toString('utf8'), {transportFinished: true, terminalRequired: true, terminal: chunk => chunk.value.event === 'done'}).complete) throw new Error('INCOMPLETE_CAPTURE_STREAM');
      }
      records.push({...entry, body, kind: 'RESPONSE', requestData: request});
      continue;
    }
    const contract = cancelContracts.find(c => c.path === entry.path && c.method === entry.method);
    const replacement = capture.entries.find(e => e.path === entry.path && e.method === entry.method && e.startedAt > entry.startedAt && e.complete && e.response?.status === 200);
    if (!entry.cancelled || entry.failure !== 'net::ERR_ABORTED' || !contract || !replacement) throw new Error('INCOMPLETE_CAPTURE_RESPONSE');
    records.push({...entry, kind: 'EXPECTED_CLIENT_CANCEL', requestData: request, cancelContract: contract.source});
  }
  const groups = new Map();
  for (const record of records) groups.set(record.signature, [...(groups.get(record.signature) ?? []), record]);
  const repeatedReads = [];
  for (const group of groups.values()) {
    if (group.length === 1) continue;
    const contract = sequenceContracts.find(c => c.path === group[0].path && c.method === group[0].method && c.kind === 'IDENTICAL_COMPLETE_READS');
    if (!contract || typeof group[0].observedDuring !== 'string' || !group[0].observedDuring || group.some(e => e.kind !== 'RESPONSE' || e.response.status !== 200 || e.observedDuring !== group[0].observedDuring || e.response.contentType !== group[0].response.contentType || e.response.body.sha256 !== group[0].response.body.sha256)) throw new Error('REPLAY_REQUIRES_GENERATION_BINDING');
    repeatedReads.push({contractId: contract.id, requestIds: group.map(e => e.id), matching: 'FULL_SIGNATURE_AND_OBSERVED_OCCURRENCE_IDENTICAL_COMPLETE_DATA'});
  }
  return {capture, records, exclusions, repeatedReads, captureDigest: hashBytes(captureBytes)};
}

/** Matches full request semantics. Unmatched calls fail closed with no live backend fallback. */
export class ReplaySequence {
  constructor(fixture) {this.fixture = fixture;this.used = new Set();}
  consume(request, phase = 'bootstrap') {
    const signature = requestSignature({...request, context: this.fixture.capture.businessContext});
    const entry = this.fixture.records.find(e => e.signature === signature && e.observedDuring === phase && !this.used.has(e.id));
    if (!entry) throw new Error('UNMATCHED_REPLAY_REQUEST');
    this.used.add(entry.id);return entry;
  }
  assertConsumed() {
    const unused = this.fixture.records.filter(e => !this.used.has(e.id));
    if (unused.length) throw new Error('UNCONSUMED_REPLAY_REQUESTS:' + unused.map(e => e.id).join(','));
  }
}
