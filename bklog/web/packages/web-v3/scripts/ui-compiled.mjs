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

import { readdirSync, readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const distCss = join(root, 'dist/assets');
const required = [
  { token: '--bklog-favorite-bg', value: '#ebeef5' },
  { token: '--bklog-manage-left-bg', value: '#f3f6fa' },
  { token: '--bklog-favorite-width', value: '240px' },
  { token: '--bklog-collection-left-width', value: '250px' },
  { token: '--bklog-header-height', value: '52px' },
  { token: '--bklog-toggle-size', value: '32px' },
  { token: '--bklog-nav-bg', value: '#182132' },
  { token: '--bklog-search-submit-size', value: '32px' },
  { token: '--bklog-chip-bg', value: '#eaebf0' },
  { token: '--bklog-highlight-bg', value: '#faeeb1' },
  { token: '--bklog-sql-bg', value: '#fafbfd' },
  { token: '--bklog-collection-add-bg', value: '#cddffe' },
  { token: '--bklog-collection-group-active', value: '#e1ecff' },
  { token: '--bklog-favorite-item-height', value: '32px' },
  { token: '--bklog-origin-row-height', value: '32px' },
  { token: '--bklog-origin-header-bg', value: '#fafbfd' },
  { token: '--bklog-manage-nav-bg', value: '#2c354d' },
  { token: '--bklog-manage-nav-width', value: '220px' },
];

const files = readdirSync(distCss).filter(name => name.endsWith('.css'));
const css = files.map(name => readFileSync(join(distCss, name), 'utf8')).join('\n').toLowerCase();
const checks = required.map(item => ({
  ...item,
  ok: css.includes(item.token) && css.includes(item.value),
}));
const report = { ok: checks.every(item => item.ok), checks, files };
const outDir = join(root, '.ai-native/ui-align/captures');
mkdirSync(outDir, { recursive: true });
writeFileSync(join(outDir, 'compiled-css.json'), `${JSON.stringify(report, null, 2)}\n`);
process.stdout.write(`${JSON.stringify(report, null, 2)}\n`);
process.exitCode = report.ok ? 0 : 1;
