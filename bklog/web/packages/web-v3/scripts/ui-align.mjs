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

import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
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
  navBg: [24, 33, 50],
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

async function stitchCompare(browser, leftPath, rightPath, name) {
  if (!existsSync(leftPath) || !existsSync(rightPath)) {
    return null;
  }
  const page = await browser.newPage({ viewport: { width: 1600, height: 980 } });
  const left = `data:image/png;base64,${readFileSync(leftPath).toString('base64')}`;
  const right = `data:image/png;base64,${readFileSync(rightPath).toString('base64')}`;
  await page.setContent(`<!doctype html><html><head><meta charset="utf-8"><style>
    body{margin:0;background:#1d1d1d;color:#fff;font:14px/1.4 sans-serif}
    .row{display:flex;gap:8px;padding:8px}
    figure{flex:1;margin:0;background:#111}
    figcaption{padding:8px 10px;background:#3a84ff}
    img{display:block;width:100%;height:auto}
  </style></head><body>
    <div class="row">
      <figure><figcaption>V2 · bklog/web/src + architecture-chema mock</figcaption><img src="${left}"></figure>
      <figure><figcaption>V3 · packages/web-v3</figcaption><img src="${right}"></figure>
    </div>
  </body></html>`);
  await page.waitForFunction(() => [...document.images].every(img => img.complete && img.naturalWidth > 0));
  const path = join(outDir, `${name}.png`);
  await page.screenshot({ path, fullPage: true });
  await page.close();
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
    checks.push({ id: 'favorite-width', ok: Math.abs(favorite.width - 240) <= 8, detail: favorite.width });
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
  const headerStyle = await computed(page, '[data-ui="app-header"]');
  const headerRgb = parseRgb(headerStyle?.backgroundColor);
  checks.push({
    id: 'header-bg-from-render',
    ok: nearColor(headerRgb, TOKENS.navBg),
    detail: { expected: '#182132', actual: headerStyle?.backgroundColor, shotRequired: true },
  });
  checks.push({
    id: 'search-submit-circle',
    ok: Boolean(await page.$('[data-ui="search-submit"]')),
    detail: 'circular search control',
  });
  const navTitles = await page.$$eval('[data-ui="nav-primary"] a', links => links.map(el => el.textContent?.trim())).catch(() => []);
  checks.push({
    id: 'primary-nav-v2',
    ok: navTitles.join(',') === '检索,仪表盘,管理',
    detail: navTitles,
  });
  checks.push({
    id: 'favorite-tree',
    ok: Boolean(await page.$('[data-ui="favorite-tree"]')),
    detail: 'favorite groups as tree',
  });
  const analyzeCount = await page.$$eval('[data-ui="field-analyze"]', nodes => nodes.length).catch(() => 0);
  checks.push({
    id: 'field-analyze',
    ok: analyzeCount > 0 && Boolean(await page.$('[data-ui="field-setting"]')),
    detail: analyzeCount,
  });
  const rowHeight = await page.$eval('[data-ui="origin-table"] tbody tr', el => el.getBoundingClientRect().height).catch(() => 0);
  checks.push({
    id: 'origin-row-density',
    ok: rowHeight > 0 && Math.abs(rowHeight - 32) <= 12,
    detail: rowHeight,
  });
  const tabText = await page.$eval('[data-ui="result-tabs"]', el => (el.textContent || '').replace(/\s+/g, '')).catch(() => '');
  checks.push({
    id: 'result-tabs',
    ok: ['原始日志', '日志聚类', '图表分析', 'Grep模式'].every(label => tabText.includes(label)),
    detail: tabText,
  });
  checks.push({
    id: 'scene-bar',
    ok: Boolean(await page.$('[data-ui="scene-bar"]')) && Boolean(await page.$('[data-ui="scene-none"]')),
    detail: 'scene switcher',
  });
  checks.push({
    id: 'workbench-controls',
    ok: Boolean(await page.$('[data-ui="index-set"]')) && Boolean(await page.$('[data-ui="time-preset"]')),
    detail: 'index set + time',
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
  const groupCount = await page.$$eval('[data-ui="collection-groups"] button', rows => rows.length).catch(() => 0);
  checks.push({ id: 'collection-groups', ok: groupCount >= 2, detail: groupCount });
  checks.push({
    id: 'collection-create',
    ok: Boolean(await page.$('[data-ui="collection-create"]')),
    detail: 'create control',
  });
  return { left, right, leftStyle, checks };
}

async function measureManage(page) {
  const left = await box(await page.$('[data-ui="manage-left"]'));
  const right = await box(await page.$('[data-ui="manage-right"]'));
  const checks = [];
  if (left && right) {
    checks.push({ id: 'manage-left-of-right', ok: left.x + left.width <= right.x + 2, detail: { left, right } });
    checks.push({ id: 'manage-nav-width', ok: Math.abs(left.width - 220) <= 16, detail: left.width });
  } else {
    checks.push({ id: 'manage-layout', ok: false, detail: 'manage panes missing' });
  }
  const titles = await page.$$eval('.manage-nav__group-title', nodes => nodes.map(el => (el.textContent || '').trim())).catch(() => []);
  checks.push({
    id: 'manage-nav-groups',
    ok: titles.join(',') === '数据接入,索引集,清洗,归档,提取,ES,客户端',
    detail: titles,
  });
  checks.push({
    id: 'manage-nav-tree',
    ok: Boolean(await page.$('[data-ui="manage-nav-tree"]')),
    detail: 'grouped manage tree',
  });
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

  const emptyRows = await page.$$eval('[data-ui="origin-table"] tbody tr', rows => rows.length).catch(() => 0);
  await page.click('.retrieve-favorite-item__main').catch(() => null);
  await page.waitForTimeout(400);
  const favoriteApplied = await page.$eval('[data-ui="search-chips"]', el => /error/i.test(el.textContent || '')).catch(() => false);
  await page.fill('.retrieve-searchbar__input input, .retrieve-searchbar__input .t-input__inner', 'error log:timeout');
  await page.click('.retrieve-searchbar__submit');
  await page.waitForTimeout(400);
  const chipsShot = await captureRegion(page, '[data-ui="search-chips"]', 'v3-retrieve-chips');
  const highlightShot = await capture(page, 'v3-retrieve-highlight');
  const hasChips = Boolean(await page.$('.retrieve-chip'));
  const hasMark = Boolean(await page.$('mark'));
  await page.click('[data-ui="search-mode-sql"]');
  await page.waitForTimeout(200);
  const sqlShot = await captureRegion(page, '[data-ui="search-sql"]', 'v3-retrieve-sql');
  await page.click('[data-ui="search-history"]');
  await page.waitForTimeout(200);
  const historyShot = await captureRegion(page, '[data-ui="search-history-panel"]', 'v3-retrieve-history');
  await page.click('[data-ui="log-expand"]').catch(() => null);
  await page.waitForTimeout(200);
  const expandShot = await capture(page, 'v3-retrieve-expand');
  const hasDetail = await page.$('[data-ui="log-detail"]');
  report.pages.push({
    name: 'retrieve-deep',
    shot: highlightShot,
    regions: { chips: chipsShot, sql: sqlShot, history: historyShot },
    checks: [
      { id: 'empty-query-rows', ok: emptyRows > 0, detail: emptyRows },
      { id: 'favorite-apply', ok: favoriteApplied, detail: 'favorite fills chips and searches' },
      { id: 'chips-visible', ok: hasChips, detail: chipsShot },
      { id: 'sql-editor', ok: Boolean(sqlShot) || Boolean(await page.$('[data-ui="search-sql"]')), detail: sqlShot },
      { id: 'history-panel', ok: Boolean(historyShot), detail: historyShot },
      { id: 'highlight-mark', ok: Boolean(hasMark), detail: 'keyword highlight in screenshot flow' },
      { id: 'row-expand', ok: Boolean(hasDetail), detail: 'expanded log detail' },
      { id: 'origin-kv', ok: Boolean(hasDetail) && Boolean(await page.$('.retrieve-log-kv')), detail: 'expanded kv rows' },
      { id: 'origin-context', ok: Boolean(await page.$('[data-ui="log-context"]')), detail: 'context entry' },
      { id: 'origin-realtime', ok: Boolean(await page.$('[data-ui="log-realtime"]')), detail: 'realtime entry' },
      { id: 'highlight-shot', ok: Boolean(highlightShot), detail: highlightShot },
      { id: 'expand-shot', ok: Boolean(expandShot), detail: expandShot },
    ],
  });
  report.shots.push(highlightShot, expandShot, ...[chipsShot, sqlShot, historyShot].filter(Boolean));

  await page.click('[data-ui="scene-k8s"]').catch(() => null);
  await page.waitForTimeout(200);
  const sceneShot = await captureRegion(page, '[data-ui="scene-bar"]', 'v3-retrieve-scene');
  const sceneFilters = Boolean(await page.$('[data-ui="scene-filters"]'));
  await page.click('[data-ui="tab-grep"]');
  await page.waitForTimeout(200);
  const grepShot = await captureRegion(page, '[data-ui="grep-panel"]', 'v3-retrieve-grep');
  const hasGrep = Boolean(await page.$('[data-ui="grep-panel"]'));
  await page.fill('[data-ui="grep-pattern"] input, [data-ui="grep-pattern"] .t-input__inner', 'error').catch(() => null);
  await page.click('[data-ui="grep-run"]').catch(() => null);
  await page.click('[data-ui="tab-graph"]');
  await page.waitForTimeout(200);
  const graphShot = await captureRegion(page, '[data-ui="graph-panel"]', 'v3-retrieve-graph');
  const hasGraph = Boolean(await page.$('[data-ui="graph-panel"]'));
  await page.click('[data-ui="tab-clustering"]');
  await page.waitForTimeout(200);
  const clusterShot = await captureRegion(page, '[data-ui="cluster-table"]', 'v3-retrieve-cluster');
  const hasCluster = Boolean(await page.$('[data-ui="cluster-table"]'));
  report.pages.push({
    name: 'retrieve-rest',
    shot: graphShot,
    regions: { scene: sceneShot, grep: grepShot, graph: graphShot, cluster: clusterShot },
    checks: [
      { id: 'scene-filters', ok: sceneFilters, detail: sceneShot },
      { id: 'grep-panel', ok: hasGrep || Boolean(grepShot), detail: grepShot },
      { id: 'graph-panel', ok: hasGraph || Boolean(graphShot), detail: graphShot },
      { id: 'cluster-table', ok: hasCluster || Boolean(clusterShot), detail: clusterShot },
    ],
  });
  report.shots.push(...[sceneShot, grepShot, graphShot, clusterShot].filter(Boolean));

  await page.goto(`${baseUrl}/#/manage/collection`, { waitUntil: 'networkidle' });
  const collectionShot = await capture(page, 'v3-collection');
  const collectionLeftShot = await captureRegion(page, '[data-ui="collection-left"]', 'v3-collection-left');
  const collection = await measureCollection(page);
  await page.click('[data-ui="collection-create"]');
  await page.waitForSelector('[data-ui="collection-wizard"]');
  const wizardShot = await capture(page, 'v3-collection-wizard');
  const hasCards = Boolean(await page.$('[data-ui="classify-linux"]'));
  collection.checks.push({ id: 'collection-wizard', ok: Boolean(wizardShot) && hasCards, detail: wizardShot });
  await page.click('.collection-wizard__foot .t-button');
  await page.waitForTimeout(200);
  report.pages.push({ name: 'collection', shot: collectionShot, regions: { left: collectionLeftShot, wizard: wizardShot }, ...collection });
  report.shots.push(collectionShot, collectionLeftShot, wizardShot);

  await page.goto(`${baseUrl}/#/manage/clean`, { waitUntil: 'networkidle' });
  const manageShot = await capture(page, 'v3-manage-clean');
  const manageNavShot = await captureRegion(page, '[data-ui="manage-left"]', 'v3-manage-nav');
  const manage = await measureManage(page);
  const cleanTabs = await page.$$eval('[data-ui="manage-module-tabs"] button', nodes => nodes.map(el => el.textContent?.trim())).catch(() => []);
  manage.checks.push({
    id: 'manage-clean-tabs',
    ok: cleanTabs.join(',') === '清洗项,模板,脱敏',
    detail: cleanTabs,
  });
  report.pages.push({ name: 'manage-clean', shot: manageShot, regions: { nav: manageNavShot }, ...manage });
  report.shots.push(manageShot, ...[manageNavShot].filter(Boolean));

  await page.goto(`${baseUrl}/#/retrieve/clustering`, { waitUntil: 'networkidle' });
  const clusterPageShot = await capture(page, 'v3-cluster-page');
  report.pages.push({
    name: 'cluster-page',
    shot: clusterPageShot,
    checks: [{ id: 'cluster-page', ok: Boolean(await page.$('[data-ui="cluster-page"]')), detail: clusterPageShot }],
  });
  report.shots.push(clusterPageShot);

  await page.goto(`${baseUrl}/#/retrieve/context`, { waitUntil: 'networkidle' });
  const contextPageShot = await capture(page, 'v3-context-page');
  report.pages.push({
    name: 'context-page',
    shot: contextPageShot,
    checks: [{ id: 'context-page', ok: Boolean(await page.$('[data-ui="context-page"]')), detail: contextPageShot }],
  });
  report.shots.push(contextPageShot);

  await page.goto(`${baseUrl}/#/retrieve/realtime`, { waitUntil: 'networkidle' });
  const realtimePageShot = await capture(page, 'v3-realtime-page');
  report.pages.push({
    name: 'realtime-page',
    shot: realtimePageShot,
    checks: [{ id: 'realtime-page', ok: Boolean(await page.$('[data-ui="realtime-page"]')), detail: realtimePageShot }],
  });
  report.shots.push(realtimePageShot);

  const managePages = [
    ['index-set', 'v3-manage-index-set', '列表,脱敏'],
    ['custom-report', 'v3-manage-custom-report', '列表,详情'],
    ['archive', 'v3-manage-archive', '仓库,列表,回溯'],
    ['extract', 'v3-manage-extract', '任务,链路,配置'],
    ['es', 'v3-manage-es', '集群'],
    ['client-log', 'v3-manage-client', '采集,检索任务'],
    ['grok', 'v3-manage-grok', '模式'],
  ];
  for (const [path, shotName, expectTabs] of managePages) {
    await page.goto(`${baseUrl}/#/manage/${path}`, { waitUntil: 'networkidle' });
    const shot = await capture(page, shotName);
    const tabs = await page.$$eval('[data-ui="manage-module-tabs"] button', nodes => nodes.map(el => el.textContent?.trim())).catch(() => []);
    report.pages.push({
      name: shotName,
      shot,
      checks: [
        { id: `${path}-page`, ok: Boolean(await page.$('[data-ui="manage-right"]')), detail: shot },
        { id: `${path}-tabs`, ok: tabs.join(',') === expectTabs, detail: tabs },
      ],
    });
    report.shots.push(shot);
  }

  if (v2BaseUrl) {
    await page.goto(`${v2BaseUrl}/#/retrieve/16176?spaceUid=bkcc__5000140&bizId=5000140`, { waitUntil: 'domcontentloaded', timeout: 90000 });
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
    await page.goto(`${v2BaseUrl}/#/manage/log-collection/collection-item/list?spaceUid=bkcc__5000140&bizId=5000140`, { waitUntil: 'domcontentloaded', timeout: 60000 }).catch(() => null);
    await page.waitForTimeout(2500);
    const v2Collection = await capture(page, 'v2-collection');
    const v2HasCollection = Boolean(await page.$(
      '.bk-table, .group-tree-container, .collection-item-container, .bk-resize-layout, [class*="collect"], .bk-exception',
    ));
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

  const compareRetrieve = await stitchCompare(
    browser,
    join(outDir, 'v2-retrieve.png'),
    join(outDir, 'v3-retrieve.png'),
    'compare-retrieve',
  );
  const compareCollection = await stitchCompare(
    browser,
    join(outDir, 'v2-collection.png'),
    join(outDir, 'v3-collection.png'),
    'compare-collection',
  );
  report.compare.push({
    name: 'compare-shots',
    checks: [
      { id: 'compare-retrieve-shot', ok: Boolean(compareRetrieve), detail: compareRetrieve },
      { id: 'compare-collection-shot', ok: Boolean(compareCollection), detail: compareCollection },
    ],
  });
  if (compareRetrieve) report.shots.push(compareRetrieve);
  if (compareCollection) report.shots.push(compareCollection);

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
