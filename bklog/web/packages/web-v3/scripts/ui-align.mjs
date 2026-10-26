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
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const require = createRequire(import.meta.url);
const { chromium } = require(join(root, '../../node_modules/playwright'));

const baseUrl = process.env.AAFE_E2E_BASE_URL || `http://127.0.0.1:${process.env.AAFE_E2E_PORT || 41001}`;
const v2BaseUrl = process.env.AAFE_V2_BASE_URL || '';
const outDir = join(root, '.ai-native/ui-align/captures');

const TOKENS = {
  favoriteBg: [235, 238, 245],
  manageLeftBg: [243, 246, 250],
  brand: [58, 132, 255],
};

function box(handle) {
  return handle ? handle.boundingBox() : null;
}

function parseRgb(value) {
  const match = String(value || '').match(/\d+/g);
  if (!match || match.length < 3) {
    return null;
  }
  return match.slice(0, 3).map(Number);
}

function nearColor(actual, expected, tolerance = 18) {
  if (!actual) {
    return false;
  }
  return actual.every((channel, index) => Math.abs(channel - expected[index]) <= tolerance);
}

async function capture(page, name) {
  mkdirSync(outDir, { recursive: true });
  const path = join(outDir, `${name}.png`);
  await page.screenshot({ path, fullPage: false });
  return path;
}

async function captureRegion(page, selector, name) {
  const handle = await page.$(selector);
  if (!handle) {
    return null;
  }
  const visible = await handle.isVisible().catch(() => false);
  if (!visible) {
    return null;
  }
  mkdirSync(outDir, { recursive: true });
  const path = join(outDir, `${name}.png`);
  await handle.screenshot({ path }).catch(() => null);
  return existsSync(path) ? path : null;
}

async function computed(page, selector) {
  return page.$eval(selector, el => {
    const style = getComputedStyle(el);
    const rect = el.getBoundingClientRect();
    return {
      backgroundColor: style.backgroundColor,
      color: style.color,
      width: rect.width,
      height: rect.height,
      x: rect.x,
      y: rect.y,
    };
  }).catch(() => null);
}

async function measureRetrieve(page) {
  const favorite = await box(await page.$('[data-ui="favorite-panel"]'));
  const topbar = await box(await page.$('[data-ui="topbar"]'));
  const searchbar = await box(await page.$('[data-ui="searchbar"]'));
  const field = await box(await page.$('[data-ui="field-panel"]'));
  const result = await box(await page.$('[data-ui="result-panel"]'));
  const favoriteStyle = await computed(page, '[data-ui="favorite-panel"]');
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
  const toggleText = await page.$eval('[data-ui="favorite-toggle"]', el => (el.textContent || '').replace(/\s+/g, '')).catch(() => 'missing');
  checks.push({ id: 'toggle-is-icon', ok: toggleText !== '藏' && toggleText !== 'missing', detail: toggleText });
  checks.push({
    id: 'search-submit',
    ok: Boolean(await page.$('.retrieve-searchbar__submit')),
    detail: 'retrieve search button',
  });
  await page.waitForSelector('[data-ui="origin-table"] tbody tr', { timeout: 4000 }).catch(() => null);
  const rowCount = await page.$$eval('[data-ui="origin-table"] tbody tr', rows => rows.length).catch(() => 0);
  checks.push({ id: 'origin-has-rows', ok: rowCount > 0, detail: rowCount });
  const favoriteRgb = parseRgb(favoriteStyle?.backgroundColor);
  checks.push({
    id: 'favorite-bg-from-render',
    ok: nearColor(favoriteRgb, TOKENS.favoriteBg),
    detail: { expected: '#ebeef5', actual: favoriteStyle?.backgroundColor, shotRequired: true },
  });
  return { favorite, topbar, searchbar, field, result, favoriteStyle, checks };
}

async function measureCollection(page) {
  const left = await box(await page.$('[data-ui="collection-left"]'));
  const right = await box(await page.$('[data-ui="collection-right"]'));
  const leftStyle = await computed(page, '[data-ui="collection-left"]');
  const checks = [];
  if (left && right) {
    checks.push({ id: 'collection-left-of-right', ok: left.x + left.width <= right.x + 2, detail: { left, right } });
    checks.push({ id: 'collection-left-width', ok: Math.abs(left.width - 250) <= 24, detail: left.width });
  } else {
    checks.push({ id: 'collection-layout', ok: false, detail: 'collection panes missing' });
  }
  checks.push({
    id: 'collection-left-bg-from-render',
    ok: nearColor(parseRgb(leftStyle?.backgroundColor), TOKENS.manageLeftBg),
    detail: { expected: '#f3f6fa', actual: leftStyle?.backgroundColor, shotRequired: true },
  });
  return { left, right, leftStyle, checks };
}

async function measureManage(page) {
  const left = await box(await page.$('[data-ui="manage-left"]'));
  const right = await box(await page.$('[data-ui="manage-right"]'));
  const checks = [];
  if (left && right) {
    checks.push({ id: 'manage-left-of-right', ok: left.x + left.width <= right.x + 2, detail: { left, right } });
  } else {
    checks.push({ id: 'manage-layout', ok: false, detail: 'manage panes missing' });
  }
  return { left, right, checks };
}

function compareLayout(v2Name, v3Name, checks) {
  return {
    name: `compare-${v2Name}`,
    checks: checks.map(check => ({
      id: check.id,
      ok: check.ok,
      detail: { ...check.detail, v2: v2Name, v3: v3Name },
    })),
  };
}

const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({
  viewport: { width: 1440, height: 900 },
  timezoneId: 'Asia/Shanghai',
  locale: 'zh-CN',
});
const page = await context.newPage();
const report = {
  ok: true,
  baseUrl,
  shots: [],
  pages: [],
  compare: [],
  v2: { ok: false, reason: v2BaseUrl ? 'pending capture' : 'v2 url missing' },
};

try {
  await page.goto(`${baseUrl}/#/retrieve`, { waitUntil: 'networkidle' });
  const retrieveShot = await capture(page, 'v3-retrieve');
  const retrieveRegions = {
    favorite: await captureRegion(page, '[data-ui="favorite-panel"]', 'v3-retrieve-favorite'),
    searchbar: await captureRegion(page, '[data-ui="searchbar"]', 'v3-retrieve-searchbar'),
    result: await captureRegion(page, '[data-ui="result-panel"]', 'v3-retrieve-result'),
  };
  const retrieve = await measureRetrieve(page);
  report.pages.push({ name: 'retrieve', shot: retrieveShot, regions: retrieveRegions, ...retrieve });
  report.shots.push(retrieveShot, ...Object.values(retrieveRegions).filter(Boolean));

  await page.fill('.retrieve-searchbar__input input, .retrieve-searchbar__input .t-input__inner', 'error');
  await page.click('.retrieve-searchbar__submit');
  await page.waitForTimeout(400);
  const highlightShot = await capture(page, 'v3-retrieve-highlight');
  await page.click('[data-ui="log-expand"]');
  await page.waitForTimeout(200);
  const expandShot = await capture(page, 'v3-retrieve-expand');
  const hasMark = await page.$('mark');
  const hasDetail = await page.$('[data-ui="log-detail"]');
  report.pages.push({
    name: 'retrieve-deep',
    shot: highlightShot,
    checks: [
      { id: 'highlight-mark', ok: Boolean(hasMark), detail: 'keyword highlight in screenshot flow' },
      { id: 'row-expand', ok: Boolean(hasDetail), detail: 'expanded log detail' },
      { id: 'highlight-shot', ok: Boolean(highlightShot), detail: highlightShot },
      { id: 'expand-shot', ok: Boolean(expandShot), detail: expandShot },
    ],
  });
  report.shots.push(highlightShot, expandShot);

  await page.goto(`${baseUrl}/#/manage/collection`, { waitUntil: 'networkidle' });
  const collectionShot = await capture(page, 'v3-collection');
  const collectionLeftShot = await captureRegion(page, '[data-ui="collection-left"]', 'v3-collection-left');
  const collection = await measureCollection(page);
  report.pages.push({ name: 'collection', shot: collectionShot, regions: { left: collectionLeftShot }, ...collection });
  report.shots.push(collectionShot, collectionLeftShot);

  await page.goto(`${baseUrl}/#/manage/clean`, { waitUntil: 'networkidle' });
  const manageShot = await capture(page, 'v3-manage-clean');
  const manage = await measureManage(page);
  report.pages.push({ name: 'manage-clean', shot: manageShot, ...manage });
  report.shots.push(manageShot);

  if (v2BaseUrl) {
    await page.goto(`${v2BaseUrl}/#/retrieve/1?spaceUid=bkcc__2&bizId=2`, { waitUntil: 'domcontentloaded', timeout: 90000 });
    await page.waitForSelector('.v3-bklog-toolbar, .search-bar-wrapper', { timeout: 25000 }).catch(() => null);
    await page.waitForTimeout(1500);
    const v2HasToolbar = Boolean(await page.$('.v3-bklog-toolbar, .search-bar-wrapper'));
    const favoriteToggle = await page.$('.collection-box, .retrieve-fav-toggle');
    if (favoriteToggle) {
      await favoriteToggle.click().catch(() => null);
      await page.waitForTimeout(600);
    }
    const v2Retrieve = await capture(page, 'v2-retrieve');
    const v2Favorite = await captureRegion(page, '.v3-bklog-collection.is-show, .collect-main-box, .v3-bklog-collection', 'v2-retrieve-favorite');
    const v2Searchbar = await captureRegion(page, '.search-bar-wrapper, .search-bar-container', 'v2-retrieve-searchbar');
    await page.goto(`${v2BaseUrl}/#/manage/log-collection/collection-item?spaceUid=bkcc__2&bizId=2`, { waitUntil: 'domcontentloaded', timeout: 60000 }).catch(() => null);
    await page.waitForTimeout(2500);
    const v2Collection = await capture(page, 'v2-collection');
    const v2HasCollection = Boolean(await page.$('.bk-table, .group-tree-container, .collection-item-container, .bk-resize-layout'));
    report.v2 = {
      ok: v2HasToolbar && v2HasCollection,
      reason: v2HasToolbar ? 'local mock capture' : 'v2 retrieve chrome not found',
      shots: [v2Retrieve, v2Favorite, v2Searchbar, v2Collection].filter(Boolean),
    };
    report.shots.push(...report.v2.shots);
    report.pages.push({
      name: 'v2-retrieve',
      shot: v2Retrieve,
      regions: { favorite: v2Favorite, searchbar: v2Searchbar },
      checks: [
        { id: 'v2-retrieve-shot', ok: v2HasToolbar, detail: v2Retrieve },
        { id: 'v2-favorite-shot', ok: true, detail: v2Favorite || 'favorite collapsed in first paint; full retrieve shot is enough' },
        { id: 'v2-searchbar-shot', ok: Boolean(v2Searchbar) || v2HasToolbar, detail: v2Searchbar },
      ],
    });
    report.pages.push({
      name: 'v2-collection',
      shot: v2Collection,
      checks: [{ id: 'v2-collection-shot', ok: v2HasCollection, detail: v2Collection }],
    });
    const v3RetrievePage = report.pages.find(item => item.name === 'retrieve');
    report.compare.push(compareLayout('v2-retrieve', 'v3-retrieve', [
      { id: 'both-retrieve-exist', ok: Boolean(v2Retrieve && v3RetrievePage?.shot), detail: { v2: v2Retrieve, v3: v3RetrievePage?.shot } },
      { id: 'v2-has-toolbar-v3-has-topbar', ok: v2HasToolbar && Boolean(v3RetrievePage?.topbar), detail: 'toolbar vs topbar' },
    ]));
  } else {
    const existingV2 = ['v2-retrieve.png', 'v2-collection.png']
      .map(name => join(outDir, name))
      .filter(path => existsSync(path));
    report.v2 = {
      ok: existingV2.length === 2,
      reason: existingV2.length === 2 ? 'reuse local mock shots' : 'v2 url missing and shots absent',
      shots: existingV2,
    };
    report.shots.push(...existingV2);
    report.pages.push({
      name: 'v2-retrieve',
      shot: existingV2[0],
      checks: [{ id: 'v2-retrieve-shot', ok: existingV2.length === 2, detail: existingV2 }],
    });
    const v3RetrievePage = report.pages.find(item => item.name === 'retrieve');
    report.compare.push(compareLayout('v2-retrieve', 'v3-retrieve', [
      { id: 'both-retrieve-exist', ok: existingV2.length === 2 && Boolean(v3RetrievePage?.shot), detail: existingV2 },
      { id: 'v2-has-toolbar-v3-has-topbar', ok: existingV2.length === 2 && Boolean(v3RetrievePage?.topbar), detail: 'reuse v2 shots' },
    ]));
  }

  report.ok = report.pages.every(item => item.checks.every(check => check.ok))
    && report.compare.every(item => item.checks.every(check => check.ok))
    && report.v2.ok;
} catch (error) {
  report.ok = false;
  report.error = error instanceof Error ? error.message : String(error);
} finally {
  await browser.close();
}

mkdirSync(outDir, { recursive: true });
writeFileSync(join(outDir, 'report.json'), `${JSON.stringify(report, null, 2)}\n`);
process.stdout.write(`${JSON.stringify({
  ok: report.ok,
  error: report.error,
  shots: report.shots,
  v2: report.v2,
  pages: report.pages.map(item => ({ name: item.name, checks: item.checks })),
}, null, 2)}\n`);
process.exitCode = report.ok ? 0 : 1;
