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

import { existsSync, readFileSync } from 'node:fs';
import { createServer } from 'node:http';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const webRoot = join(dirname(fileURLToPath(import.meta.url)), '../../..');
const port = Number(process.env.AAFE_V2_MOCK_PORT || 41091);
const mockRoots = [
  process.env.AAFE_V2_MOCK_ROOT,
  join(webRoot, '.e2e-skills/assets/architecture-chema/mock'),
  join(webRoot, '.docs/architecture-chema/mock'),
].filter(Boolean);

const mockRoot = mockRoots.find(dir => existsSync(join(dir, 'retrieve-16176/manifest.json')));
if (!mockRoot) {
  throw new Error('missing .e2e-skills/assets/architecture-chema/mock/retrieve-16176');
}

const EMPTY = { result: true, code: 0, message: '', data: {} };

function loadScene(name) {
  const sceneDir = join(mockRoot, name);
  const manifest = JSON.parse(readFileSync(join(sceneDir, 'manifest.json'), 'utf8'));
  return (manifest.records || []).flatMap(item => {
    const file = join(sceneDir, item.file);
    if (!existsSync(file)) {
      return [];
    }
    return [JSON.parse(readFileSync(file, 'utf8'))];
  });
}

const records = [...loadScene('retrieve-16176'), ...loadScene('manage-log-collection')];

function match(url) {
  let parsed;
  try {
    parsed = new URL(url, 'http://127.0.0.1');
  } catch {
    return null;
  }
  const same = records.filter(item => item.pathname === parsed.pathname);
  if (!same.length) {
    return null;
  }
  return same.find(item => (item.search || '') === parsed.search) || same[same.length - 1];
}

const server = createServer((req, res) => {
  if (req.method === 'OPTIONS') {
    res.writeHead(204, {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Headers': '*',
      'Access-Control-Allow-Methods': '*',
    });
    res.end();
    return;
  }
  const record = match(req.url || '/');
  process.stdout.write(`${req.method} ${req.url} -> ${record ? record.pathname : 'EMPTY'}\n`);
  const body = record?.body ?? EMPTY;
  res.writeHead(record?.status || 200, {
    'Content-Type': 'application/json; charset=utf-8',
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Headers': '*',
    'Access-Control-Allow-Methods': '*',
  });
  res.end(typeof body === 'string' ? body : JSON.stringify(body));
});

server.listen(port, '127.0.0.1', () => {
  process.stdout.write(`v2-scene-mock ${mockRoot} http://127.0.0.1:${port} records=${records.length}\n`);
});
