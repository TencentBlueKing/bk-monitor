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

import { mkdirSync, writeFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const require = createRequire(import.meta.url);
const { chromium } = require(join(root, '../../node_modules/playwright'));

const baseUrl = process.env.AAFE_E2E_BASE_URL || `http://127.0.0.1:${process.env.AAFE_E2E_PORT || 41001}`;
const outDir = join(root, '.ai-native/ui-align/captures');

function box(handle) {
  return handle ? handle.boundingBox() : null;
}

async function capture(page, name) {
  mkdirSync(outDir, { recursive: true });
  const path = join(outDir, `${name}.png`);
  await page.screenshot({ path, fullPage: false });
  return path;
}

async function measureRetrieve(page) {
  const favorite = await box(await page.$('[data-ui="favorite-panel"]'));
  const topbar = await box(await page.$('[data-ui="topbar"]'));
  const searchbar = await box(await page.$('[data-ui="searchbar"]'));
  const field = await box(await page.$('[data-ui="field-panel"]'));
  const result = await box(await page.$('[data-ui="result-panel"]'));
  const checks = [];
  if (favorite && topbar) {
    checks.push({ id: 'favorite-left-of-main', ok: favorite.x + favorite.width <= topbar.x + 2, detail: { favorite, topbar } });
    checks.push({ id: 'favorite-width', ok: Math.abs(favorite.width - 240) <= 24, detail: favorite.width });
  } else {
    checks.push({ id: 'favorite-visible', ok: false, detail: 'favorite panel missing' });
  }
  if (topbar && searchbar) {
    checks.push({ id: 'searchbar-below-topbar', ok: searchbar.y >= topbar.y + topbar.height - 2, detail: { topbar, searchbar } });
  }
  if (field && result) {
    checks.push({ id: 'field-left-of-result', ok: field.x + field.width <= result.x + 2, detail: { field, result } });
  }
  return { favorite, topbar, searchbar, field, result, checks };
}

async function measureCollection(page) {
  const left = await box(await page.$('[data-ui="collection-left"]'));
  const right = await box(await page.$('[data-ui="collection-right"]'));
  const checks = [];
  if (left && right) {
    checks.push({ id: 'collection-left-of-right', ok: left.x + left.width <= right.x + 2, detail: { left, right } });
    checks.push({ id: 'collection-left-width', ok: Math.abs(left.width - 250) <= 24, detail: left.width });
  } else {
    checks.push({ id: 'collection-layout', ok: false, detail: 'collection panes missing' });
  }
  return { left, right, checks };
}

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
const report = { ok: true, baseUrl, pages: [] };

try {
  await page.goto(`${baseUrl}/#/retrieve`, { waitUntil: 'networkidle' });
  const retrieveShot = await capture(page, 'v3-retrieve');
  const retrieve = await measureRetrieve(page);
  report.pages.push({ name: 'retrieve', shot: retrieveShot, ...retrieve });

  await page.goto(`${baseUrl}/#/manage/collection`, { waitUntil: 'networkidle' });
  const collectionShot = await capture(page, 'v3-collection');
  const collection = await measureCollection(page);
  report.pages.push({ name: 'collection', shot: collectionShot, ...collection });

  report.ok = report.pages.every(item => item.checks.every(check => check.ok));
} catch (error) {
  report.ok = false;
  report.error = error instanceof Error ? error.message : String(error);
} finally {
  await browser.close();
}

mkdirSync(outDir, { recursive: true });
writeFileSync(join(outDir, 'report.json'), `${JSON.stringify(report, null, 2)}\n`);
process.stdout.write(`${JSON.stringify({ ok: report.ok, error: report.error, pages: report.pages.map(item => ({ name: item.name, checks: item.checks })) }, null, 2)}\n`);
process.exitCode = report.ok ? 0 : 1;
