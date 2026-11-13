import { localArtifactPath } from './local-artifacts.mjs';
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

import { readFileSync, realpathSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { isAbsolute, relative, resolve, sep } from 'node:path';
import { spawnSync } from 'node:child_process';

export const hashFile = file => createHash('sha256').update(readFileSync(file)).digest('hex');

export function safePath(root, path) {
  if (typeof path !== 'string' || !path || isAbsolute(path) || path.split(/[\\/]/).includes('..')) {
    throw Error(`Unsafe relative path: ${path}`);
  }
  const target = realpathSync(resolve(root, path));
  const inside = relative(realpathSync(root), target);
  if (!inside || inside.startsWith(`..${sep}`) || inside === '..' || isAbsolute(inside)) {
    throw Error(`Path escapes root: ${path}`);
  }
  return target;
}

export function normalizeChange(webRoot, path) {
  const normalized = path.replaceAll('\\', '/');
  const local = normalized.startsWith('bklog/web/') ? normalized.slice('bklog/web/'.length) : normalized;
  if (!local || local.split('/').includes('..')) throw Error(`Unsafe changed path: ${path}`);
  const inside = relative(resolve(webRoot), isAbsolute(local) ? resolve(local) : resolve(webRoot, local));
  if (!inside || inside === '..' || inside.startsWith(`..${sep}`) || isAbsolute(inside)) {
    throw Error(`Changed path outside web: ${path}`);
  }
  return inside.split(sep).join('/');
}

const matches = (rule, file) => rule.exact.includes(file) || rule.prefixes.some(p => file.startsWith(p));

export function selectGroups(manifest, changes) {
  if (!changes.length) return { groups: manifest.groups, unmapped: [] };
  const ids = new Set();
  const unmapped = [];
  for (const file of changes) {
    const applicable = matches(manifest.commonImpact, file)
      ? manifest.groups : manifest.groups.filter(group => matches(group, file));
    if (!applicable.length) unmapped.push(file);
    for (const group of applicable) ids.add(group.id);
  }
  return { groups: manifest.groups.filter(group => ids.has(group.id)), unmapped };
}

export function verifyManifest(manifest, webRoot, baselineRoot) {
  if (manifest.schemaVersion !== 1 || !manifest.groups?.length || manifest.businessAccepted !== false ||
      manifest.visualAccepted !== false || !manifest.evidence?.length || !manifest.sourceSnapshot?.length) {
    throw Error('Invalid partial baseline manifest');
  }
  const unique = (values, label) => {
    if (values.length !== new Set(values).size) throw Error(`Duplicate ${label}`);
  };
  unique(manifest.groups.map(g => g.id), 'groups');
  const files = [];
  for (const group of manifest.groups) {
    if (!group.tests?.length || !Array.isArray(group.prefixes) || !Array.isArray(group.exact)) {
      throw Error(`Invalid group: ${group.id}`);
    }
    for (const test of group.tests) {
      if (!test.file.endsWith('.test.mjs') || !test.requiredCases?.length ||
          test.requiredCases.some(id => typeof id !== 'string' || !id)) throw Error('Invalid test contract');
      safePath(webRoot, test.file);
      unique(test.requiredCases, 'case names');
      files.push(test.file);
    }
  }
  unique(files, 'test entrypoints');
  const evidence = manifest.evidence.map(item => {
    const actual = hashFile(/^(runs|source)\//.test(item.path) ? localArtifactPath(item.path) : safePath(baselineRoot, item.path));
    if (actual !== item.sha256) throw Error(`Evidence checksum mismatch: ${item.path}`);
    return { path: item.path, sha256: actual };
  });
  return { evidence, source: snapshot(manifest, webRoot) };
}

export function snapshot(manifest, webRoot) {
  return manifest.sourceSnapshot.map(item => {
    try {
      const sha256 = hashFile(safePath(webRoot, item.file));
      return { file: item.file, sha256, changedFromReference: sha256 !== item.sha256 };
    } catch (error) {
      return { file: item.file, sha256: null, changedFromReference: true, error: error.message };
    }
  });
}

export function assessTap(stdout, requiredCases, exitCode) {
  const passed = [...stdout.matchAll(/^ok \d+ - (.+)$/gm)].map(m => m[1]);
  const missing = requiredCases.filter(id => passed.filter(p => p === id).length !== 1);
  const unexpected = passed.filter(id => !requiredCases.includes(id));
  const skipped = /^(?:not )?ok \d+ - .*#\s*(?:SKIP|TODO)\b/im.test(stdout) ||
    /^# (?:skipped|todo) [1-9]\d*\s*$/im.test(stdout);
  return {
    passed: passed.length, required: requiredCases.length, missing, unexpected, skipped,
    valid: exitCode === 0 && requiredCases.length > 0 && !missing.length && !unexpected.length && !skipped &&
      passed.length === requiredCases.length,
  };
}

export function runGroups(groups, webRoot) {
  return groups.flatMap(group => group.tests.map(test => {
    const file = safePath(webRoot, test.file);
    const sha256Before = hashFile(file);
    const result = spawnSync(process.execPath, ['--test', '--test-reporter=tap', file], {
      cwd: resolve(webRoot, 'packages/web-v3'), encoding: 'utf8', maxBuffer: 16 * 1024 * 1024, timeout: 60000,
    });
    const assessment = assessTap(result.stdout ?? '', test.requiredCases, result.status);
    const sha256After = hashFile(file);
    return {
      group: group.id, file: test.file, ...assessment,
      valid: assessment.valid && sha256Before === sha256After,
      sha256Before, sha256After, exitCode: result.status,
      error: result.error?.message, stdout: result.stdout, stderr: result.stderr,
    };
  }));
}
