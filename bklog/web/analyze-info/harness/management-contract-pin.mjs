import { localArtifactUrl } from './local-artifacts.mjs';
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
import {createHash} from 'node:crypto';

// Pin the complete management recipe, including the selected scenario, rather
// than accepting old screenshots after the actor or comparison policy changes.
const commonFiles = [
 'harness/management-contract-pin.mjs', 'harness/management-menu-pilot.mjs',
 'harness/ui-snapshot.mjs', 'harness/protocol.mjs', 'harness/network-recorder.mjs',
 'harness/runtime-target.mjs', 'harness/local-artifacts.mjs', 'harness/response-classifier.mjs', 'harness/capture-transport.mjs',
 'harness/capture-management-pilot.mjs', 'harness/self-replay-management.mjs',
 'harness/replay-capture.mjs', 'harness/replay-transport.mjs', 'harness/management-baseline.mjs',
 'spec/read-policy.json', 'spec/cancel-contracts.json', 'spec/sequence-contracts.json',
];
const scenarios = new Map([
 ['management-linux-menu-stop-preview-cancel', 'scenarios/management-menu-cancel.json'],
 ['management-collapsed-nav-cluster-read', 'scenarios/management-nav-cluster-read.json'],
]);
const hash = bytes => createHash('sha256').update(bytes).digest('hex');
export function snapshotManagementContract(scenarioId, read = path => readFileSync(path.startsWith('scenarios/') ? localArtifactUrl(path) : new URL('../' + path, import.meta.url))) {
 const scenarioPath = scenarios.get(scenarioId);
 if (!scenarioPath) throw new Error('MANAGEMENT_SCENARIO_NOT_REVIEWED');
 const entries = [...commonFiles, scenarioPath].map(path => ({path, sha256: hash(read(path))}));
 return {schemaVersion: 1, kind: 'MANAGEMENT_ORACLE_TOOL_POLICY_SCENARIO', scenarioId, entries, digest: hash(JSON.stringify(entries))};
}
export function verifyManagementContract(pin, scenarioId, read) {
 const current = snapshotManagementContract(scenarioId, read);
 if (!pin || JSON.stringify(pin) !== JSON.stringify(current)) throw new Error('MANAGEMENT_CONTRACT_CHANGED_OR_MISSING');
 return current.digest;
}
