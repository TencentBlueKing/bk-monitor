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

import { createRequire } from 'node:module';
import { cpSync, existsSync, readdirSync, readFileSync, statSync, mkdirSync, writeFileSync } from 'node:fs';
import { resolve, dirname, relative } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createHash } from 'node:crypto';

const web = resolve(dirname(fileURLToPath(import.meta.url)), '../..');
const require = createRequire(resolve(web, 'package.json'));
const source = dirname(require.resolve('@blueking/log-web'));
const target = resolve(web, 'packages/web-v3/public/legacy-v1/assets');
const manifestPath = resolve(target, '../sealed-manifest.json');
const hash = path => createHash('sha256').update(readFileSync(path)).digest('hex');
function inventory(root) {
  function scan(dir) {
    return readdirSync(dir, { withFileTypes: true }).sort((a,b) => a.name.localeCompare(b.name)).flatMap(entry => {
      const file = resolve(dir, entry.name);
      if (entry.isSymbolicLink()) throw new Error('Symlinks are not supported in a sealed artifact');
      return entry.isDirectory() ? scan(file) : [{ path: relative(root, file), bytes: statSync(file).size, sha256: hash(file) }];
    });
  }
  return scan(root);
}
if (process.argv.includes('--verify')) {
  const manifest = JSON.parse(readFileSync(manifestPath, 'utf8'));
  if (JSON.stringify(inventory(target)) !== JSON.stringify(manifest.files)) throw new Error('Sealed V1 files changed');
  console.log(`Verified ${manifest.files.length} sealed V1 files`);
} else {
  if (existsSync(manifestPath)) throw new Error('V1 is already sealed; verify it instead of replacing it implicitly');
  const entry = require('@blueking/log-web');
  for (const name of [entry.entryJs, entry.entryCss]) {
    if (!name || name.includes('..') || !existsSync(resolve(source, name))) throw new Error('Invalid V1 entry manifest');
  }
  const pkg = require('@blueking/log-web/package.json');
  mkdirSync(dirname(target), { recursive: true });
  cpSync(source, target, { recursive: true, errorOnExist: true, force: false });
  const manifest = { schemaVersion: 1, package: pkg.name, version: pkg.version, entry,
    provenance: 'Installed published package used by Vue2 retrieve/container; Git provenance of published bundle not independently verified',
    command: 'node migration-project/migration-engine/freeze-v1.mjs',
    hostReady: false, files: inventory(target) };
  writeFileSync(manifestPath, JSON.stringify(manifest, null, 2) + '\n');
  console.log(`Sealed ${manifest.files.length} V1 files. Host and bridge still require implementation and acceptance.`);
}
