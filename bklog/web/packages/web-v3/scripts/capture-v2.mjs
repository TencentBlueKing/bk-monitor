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

import { existsSync, mkdirSync, writeFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { dirname, join } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const webRoot = join(root, '../..');
const require = createRequire(import.meta.url);
const { chromium } = require(join(webRoot, 'node_modules/playwright'));

const mockToolCandidates = [
  process.env.AAFE_MOCK_TOOL,
  join(webRoot, '.aafe/docs/architecture-chema/工具/load-mock-scene.mjs'),
  join(webRoot, '.e2e-skills/assets/architecture-chema/工具/load-mock-scene.mjs'),
  join(webRoot, '.docs/architecture-chema/工具/load-mock-scene.mjs'),
].filter(Boolean);
const mockTool = mockToolCandidates.find(path => existsSync(path));
if (!mockTool) {
  throw new Error(`missing mock scene loader. tried: ${mockToolCandidates.join(', ')}`);
}
const { loadMockScene, installMockRoutes } = await import(pathToFileURL(mockTool).href);

const baseUrl = process.env.AAFE_V2_BASE_URL || `http://127.0.0.1:${process.env.AAFE_E2E_PORT || 41001}`;
const outDir = join(root, '.ai-native/ui-align/captures');
const retrieveScene = await loadMockScene({ scene: 'retrieve-16176', baseUrl });
const collectionScene = await loadMockScene({ scene: 'manage-log-collection', baseUrl });
const retrieveUrl = retrieveScene.entryUrl;
const collectionUrl = collectionScene.entryUrl;
const mergedScene = {
  ...retrieveScene,
  records: [...retrieveScene.records, ...collectionScene.records],
};

mkdirSync(outDir, { recursive: true });

const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({
  viewport: { width: 1440, height: 900 },
  timezoneId: 'Asia/Shanghai',
  locale: 'zh-CN',
});
const page = await context.newPage();
const result = {
  ok: false,
  retrieveUrl,
  collectionUrl,
  shots: [],
  selectors: {},
  console: [],
  failed: [],
};
page.on('console', msg => {
  if (['error', 'warning'].includes(msg.type())) {
    result.console.push({ type: msg.type(), text: msg.text() });
  }
});
page.on('requestfailed', req => {
  result.failed.push({ url: req.url(), error: req.failure()?.errorText });
});
page.on('pageerror', err => {
  result.console.push({ type: 'pageerror', text: String(err) });
});
await installMockRoutes(page, mergedScene);

try {
  await page.goto(retrieveUrl, { waitUntil: 'domcontentloaded', timeout: 90000 });
  await page.waitForSelector('.v3-bklog-toolbar, .search-bar-wrapper, .retrieve-v3-container', { timeout: 45000 });
  await page.waitForTimeout(2000);
  const favoriteToggle = await page.$('.collection-box, .retrieve-fav-toggle, .bklog-shoucangjia');
  if (favoriteToggle) {
    await favoriteToggle.click().catch(() => null);
    await page.waitForTimeout(800);
  }
  const retrievePath = join(outDir, 'v2-retrieve.png');
  await page.screenshot({ path: retrievePath, fullPage: false });
  result.shots.push(retrievePath);
  result.selectors.toolbar = Boolean(await page.$('.v3-bklog-toolbar, .search-bar-wrapper'));
  result.selectors.favorite = Boolean(await page.$('.v3-bklog-collection, .collect-main-box'));
  result.selectors.searchbar = Boolean(await page.$('.search-bar-wrapper, .search-bar-container'));

  const favorite = await page.$('.v3-bklog-collection.is-show, .collect-main-box, .v3-bklog-collection');
  if (favorite && await favorite.isVisible().catch(() => false)) {
    const favoritePath = join(outDir, 'v2-retrieve-favorite.png');
    await favorite.screenshot({ path: favoritePath }).catch(() => null);
    if (existsSync(favoritePath)) result.shots.push(favoritePath);
  }
  const searchbar = await page.$('.search-bar-wrapper, .search-bar-container');
  if (searchbar && await searchbar.isVisible().catch(() => false)) {
    const searchbarPath = join(outDir, 'v2-retrieve-searchbar.png');
    await searchbar.screenshot({ path: searchbarPath }).catch(() => null);
    if (existsSync(searchbarPath)) result.shots.push(searchbarPath);
  }

  await page.goto(collectionUrl, { waitUntil: 'domcontentloaded', timeout: 60000 });
  await page.waitForTimeout(3000);
  const collectionPath = join(outDir, 'v2-collection.png');
  await page.screenshot({ path: collectionPath, fullPage: false });
  result.shots.push(collectionPath);
  result.selectors.collection = Boolean(await page.$(
    '.bk-table, .group-tree-container, .bk-resize-layout, .collect-container, [class*="collect"], .bk-exception, .empty-exception',
  ));
  result.ok = result.selectors.toolbar && existsSync(retrievePath) && existsSync(collectionPath);
} catch (error) {
  result.error = error instanceof Error ? error.message : String(error);
} finally {
  writeFileSync(join(outDir, 'v2-capture.json'), `${JSON.stringify(result, null, 2)}\n`);
  await browser.close();
}

process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
process.exitCode = result.ok ? 0 : 1;
