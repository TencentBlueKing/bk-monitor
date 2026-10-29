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

import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const webRoot = resolve(dirname(fileURLToPath(import.meta.url)), '../..');
const files = [
  'src/router/retrieve.js',
  'src/router/monitor.js',
  'src/router/dashboard.js',
  'src/router/manage.js',
  'src/router/index.js',
];

const items = [];
for (const file of files) {
  const cleaned = readFileSync(resolve(webRoot, file), 'utf8')
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .replace(/^\s*\/\/.*$/gm, '');
  const re = /path:\s*['"]([^'"]+)['"]/g;
  let match = re.exec(cleaned);
  while (match) {
    const nextPath = cleaned.indexOf('path:', match.index + 5);
    const slice = cleaned.slice(match.index, nextPath === -1 ? cleaned.length : nextPath);
    const name = slice.match(/name:\s*['"]([^'"]+)['"]/);
    if (name) {
      const title = slice.match(/title:\s*['"]([^'"]+)['"]/);
      const lineStart = cleaned.lastIndexOf('\n', match.index) + 1;
      const indent = cleaned.slice(lineStart, match.index).match(/^ */)?.[0].length ?? 0;
      items.push({ file, path: match[1], name: name[1], title: title?.[1] || '', indent });
    }
    match = re.exec(cleaned);
  }
}

const stack = [];
for (const item of items) {
  while (stack.length && stack.at(-1).indent >= item.indent) stack.pop();
  const parent = stack.at(-1);
  item.fullPath = item.path.startsWith('/') || item.path === '*'
    ? item.path
    : `${(parent?.fullPath || '').replace(/\/$/, '')}/${item.path}`.replace(/\/+/g, '/');
  stack.push(item);
}

const routes = items.map(({ file, name, title, fullPath }) => ({ file, name, title, path: fullPath }));
const names = new Set(routes.map(route => route.name));
if (names.size !== routes.length) {
  throw new Error(`duplicate route name: ${routes.length - names.size}`);
}

const target = resolve(webRoot, 'packages/web-v3/src/router/legacy-routes.json');
mkdirSync(dirname(target), { recursive: true });
writeFileSync(target, `${JSON.stringify(routes, null, 2)}\n`);
console.log(`routes=${routes.length}`);
