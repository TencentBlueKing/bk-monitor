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

import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, writeFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { resolve } from 'node:path';
import { normalizeChange, selectGroups, assessTap, verifyManifest, hashFile, safePath } from '../regression-baseline.mjs';

test('baseline impact: shared changes select all; unknown changes remain unmapped', () => {
  const groups = [{ id: 'a', prefixes: ['src/a/'], exact: [] }, { id: 'b', prefixes: ['src/b/'], exact: [] }];
  const spec = { groups, commonImpact: { prefixes: ['src/shared/'], exact: ['package.json'] } };
  assert.deepEqual(selectGroups(spec, ['src/a/x.ts']).groups.map(g => g.id), ['a']);
  assert.equal(selectGroups(spec, ['src/shared/x.ts']).groups.length, 2);
  assert.deepEqual(selectGroups(spec, ['src/new/x.ts']).unmapped, ['src/new/x.ts']);
});

test('baseline paths: repository and absolute changes normalize; traversal rejected', () => {
  assert.equal(normalizeChange('/web', 'bklog/web/src/a.ts'), 'src/a.ts');
  assert.equal(normalizeChange('/web', '/web/src/a.ts'), 'src/a.ts');
  for (const path of ['', '../outside.ts', '/outside.ts']) assert.throws(() => normalizeChange('/web', path));
  assert.throws(() => safePath('/web', '../outside.ts'));
});

test('baseline TAP: missing extra duplicate skipped TODO empty and failed tests cannot pass', () => {
  assert.equal(assessTap('ok 1 - a\nok 2 - b\n# skipped 0\n# todo 0\n', ['a', 'b'], 0).valid, true);
  for (const [tap, expected, code] of [
    ['ok 1 - a\n', ['a', 'b'], 0], ['ok 1 - a\nok 2 - b\n', ['a'], 0],
    ['ok 1 - a\nok 2 - a\n', ['a'], 0], ['ok 1 - a # SKIP\n', ['a'], 0],
    ['ok 1 - a # TODO\n', ['a'], 0], ['', [], 0], ['ok 1 - a\n', ['a'], 1],
  ]) assert.equal(assessTap(tap, expected, code).valid, false);
});

test('baseline integrity: changed source is stale; altered missing evidence and duplicate entries fail', () => {
  const root = mkdtempSync(resolve(tmpdir(), 'bklog-baseline-'));
  try {
    for (const file of ['a.test.mjs', 'source.ts', 'evidence.json']) writeFileSync(resolve(root, file), 'original');
    const spec = {
      schemaVersion: 1, businessAccepted: false, visualAccepted: false,
      groups: [{ id: 'a', prefixes: [], exact: [], tests: [{ file: 'a.test.mjs', requiredCases: ['case'] }] }],
      evidence: [{ path: 'evidence.json', sha256: hashFile(resolve(root, 'evidence.json')) }],
      sourceSnapshot: [{ file: 'source.ts', sha256: hashFile(resolve(root, 'source.ts')) }],
    };
    assert.equal(verifyManifest(spec, root, root).source[0].changedFromReference, false);
    writeFileSync(resolve(root, 'source.ts'), 'changed');
    assert.equal(verifyManifest(spec, root, root).source[0].changedFromReference, true);
    assert.throws(() => verifyManifest({ ...spec, groups: [...spec.groups, ...spec.groups] }, root, root));
    writeFileSync(resolve(root, 'evidence.json'), 'tampered');
    assert.throws(() => verifyManifest(spec, root, root), /checksum/);
    rmSync(resolve(root, 'evidence.json'));
    assert.throws(() => verifyManifest(spec, root, root));
  } finally { rmSync(root, { recursive: true, force: true }); }
});
