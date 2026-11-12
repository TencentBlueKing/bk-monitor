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

import {createRequire} from 'node:module';
import {mkdirSync, readFileSync, writeFileSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
const require = createRequire(new URL('../../packages/web-v3/package.json', import.meta.url));
const {chromium, expect} = require('@playwright/test');
const requested = process.argv[2];
if (!requested || new URL(requested).hostname !== 'appdev.woa.com') throw new Error('CONTROLLED_FIXTURE_TARGET_REQUIRED');
const target = new URL('/__fixtures__/native-model-contract', new URL(requested).origin).href;
const browser = await chromium.launch({headless: true, executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
const checks = [], failures = [], blocked = [], runtimeErrors = [];
const {createHash} = await import('node:crypto');
const trackedSource = ['../../packages/web-v3/fixtures/native-tree-contract.tsx', '../../packages/web-v3/src/platform/compat/tdesign/runtime-contract.ts', '../../packages/web-v3/fixtures/native-model-contract.vue', '../../packages/web-v3/src/platform/compat/vue3-component-model.ts', '../../packages/web-v3/fixtures/native-model-contract.ts', '../../packages/web-v3/fixtures/native-model-contract.html', '../../packages/web-v3/src/shared/composables/use-visible-input-focus.ts'];
const sourceDigests = () => trackedSource.map(path => createHash('sha256').update(readFileSync(new URL(path, import.meta.url))).digest('hex'));
const initialSource = sourceDigests();
let page;
try {
  const context = await browser.newContext({viewport: {width: 1440, height: 900}, locale: 'zh-CN', serviceWorkers: 'block'});
  await context.route('**/*', async route => {
    const request = route.request(), url = new URL(request.url());
    if (url.origin !== new URL(target).origin || request.method() !== 'GET' || ['xhr', 'fetch', 'ping'].includes(request.resourceType()) || url.pathname.startsWith('/api/')) {
      blocked.push({method: request.method(), path: url.pathname});await route.abort('blockedbyclient');
    } else await route.continue();
  });
  page = await context.newPage();
  await page.clock.setFixedTime(1794355200000);
  page.setDefaultTimeout(7000);
  page.on('pageerror', error => runtimeErrors.push(error.message.slice(0, 500)));
  page.on('console', message => {if (message.type() === 'error') runtimeErrors.push(message.text().replace(/https?:[^ ]+/g, '<url>').slice(0, 500));});
  await page.goto(target, {waitUntil: 'domcontentloaded', timeout: 60000});
  await expect(page.getByRole('heading', {name: '原生 TDesign 交互验证', exact: true})).toBeVisible({timeout: 20000});
  const check = async (id, action) => {try {await action();checks.push({id, passed: true});} catch (error) {checks.push({id, passed: false});failures.push({id, reason: error.message.slice(0, 600)});}};
  await check('native-clock-svg-bubbling', async () => {
    const button = page.getByTestId('clock-icon-button'), counter = page.getByTestId('clock-icon-clicks');
    await button.click();await expect(counter).toHaveText('0'); // Known fixed-Date negative control.
    await page.clock.setSystemTime(1794355200001);
    await expect.poll(() => page.evaluate(() => Date.now())).toBeGreaterThan(1794355200001);
    await button.click();await expect(counter).toHaveText('1');
  });
  await check('native-checkbox-model', async () => {
    const checkbox = page.getByRole('checkbox', {name: '禁用提交', exact: true});
    await page.getByText('禁用提交', {exact: true}).click();
    await expect(checkbox).toBeChecked();await expect(page.getByRole('button', {name: '提交', exact: true})).toBeDisabled();
    await page.getByText('禁用提交', {exact: true}).click();
    await expect(checkbox).not.toBeChecked();await expect(page.getByRole('button', {name: '提交', exact: true})).toBeEnabled();
  });
  await check('native-checkbox-group-model', async () => {
    await page.getByText('字段 A', {exact: true}).click();
    await expect(page.getByTestId('selected')).toHaveText('已选：a');
    await page.getByText('字段 B', {exact: true}).click();
    await expect(page.getByTestId('selected')).toHaveText('已选：a,b');
  });
  await check('native-radio-group-model', async () => {
    await page.getByText('SQL', {exact: true}).click();
    await expect(page.getByTestId('query-mode')).toHaveText('模式：sql');
  });
  await check('native-input-trim-enter-model', async () => {
    const input = page.getByPlaceholder('输入检索名称后按 Enter', {exact: true});
    await input.fill(' migration model ');await input.press('Enter');
    await expect(page.getByText('已提交名称：migration model', {exact: true})).toBeVisible();
  });
  await check('native-select-model', async () => {
    await page.getByTestId('native-select').click();await page.getByText('日志', {exact: true}).click();
    await expect(page.getByTestId('native-selected-index')).toHaveText('索引：logs');
  });
  await check('native-switch-model', async () => {
    await page.getByTestId('native-switch').click();
    await expect(page.getByTestId('native-refresh')).toHaveText('刷新：true');
  });
  await check('native-tag-input-model', async () => {
    const input = page.getByPlaceholder('新增字段', {exact: true});await input.fill('level');await input.press('Enter');
    await expect(page.getByTestId('native-tags')).toHaveText('字段：level');
  });
  await check('native-model-reset', async () => {
    await page.getByRole('button', {name: '重置', exact: true}).click();
    await expect(page.getByTestId('selected')).toHaveText('已选：无');
    await expect(page.getByTestId('query-mode')).toHaveText('模式：ui');
    await expect(page.getByRole('checkbox', {name: '禁用提交', exact: true})).not.toBeChecked();
  });
  await check('native-tree-scoped-label', async () => {
    await page.getByRole('button',{name:'Mount test field tree',exact:true}).click();
    const tree=page.getByTestId('native-tree-contract');
    const parent=tree.getByText('Tree node parent',{exact:true}), leaf=tree.getByText('Tree node leaf',{exact:true});
    await expect(parent).toBeVisible();await expect(leaf).toBeVisible();
    const search=tree.getByPlaceholder('Filter test field tree',{exact:true});
    await search.fill('absent');await expect(leaf).not.toBeVisible();
    await search.fill('leaf');await expect(leaf).toBeVisible();
    await search.fill('');await parent.click();await expect(leaf).not.toBeVisible();
    await parent.click();await expect(leaf).toBeVisible();
  });
  await check('popup-visible-focus', async () => {
    await page.getByRole('button', {name: '挂载隐藏浮层', exact: true}).click();
    const input = page.getByPlaceholder('浮层内聚焦输入', {exact: true});
    await expect(input).toHaveCount(1);await expect(input).not.toBeVisible();await expect(input).not.toBeFocused();
    await page.getByRole('button', {name: '显示浮层', exact: true}).click();
    await expect(input).toBeVisible();await expect(input).toBeFocused();
    await page.getByRole('button', {name: '关闭浮层', exact: true}).click();await expect(input).toHaveCount(0);
  });
  await check('popup-focus-cleanup', async () => {
    await page.getByRole('button', {name: '挂载隐藏浮层', exact: true}).click();
    await page.getByRole('button', {name: '关闭浮层', exact: true}).click();
    const reveal = page.getByRole('button', {name: '显示浮层', exact: true});await reveal.click();
    await expect(page.getByPlaceholder('浮层内聚焦输入', {exact: true})).toHaveCount(0);await expect(reveal).toBeFocused();
  });
} catch (error) {failures.push({id: 'fixture-initialization', reason: error.message.slice(0, 700)});}
finally {
  if (JSON.stringify(initialSource) !== JSON.stringify(sourceDigests())) failures.push({id: 'source-integrity', reason: 'SOURCE_CHANGED_DURING_CALIBRATION'});
  const out = fileURLToPath(new URL('../runs/calibration/native-model/', import.meta.url));mkdirSync(out, {recursive: true});
  await page?.screenshot({path: out + `/screen-${Date.now()}.png`}).catch(() => {});
  await browser.close();
  const requiredIds = ['native-tree-scoped-label', 'native-clock-svg-bubbling','native-checkbox-model','native-checkbox-group-model','native-radio-group-model','native-input-trim-enter-model','native-select-model','native-switch-model','native-tag-input-model','native-model-reset','popup-visible-focus','popup-focus-cleanup'];
  const missing = requiredIds.filter(id => checks.filter(check => check.id === id && check.passed).length !== 1);
  if (missing.length) failures.push({id:'required-checks', missing});
  if (blocked.length || runtimeErrors.length) failures.push({id:'fixture-integrity', blocked:blocked.length, runtimeErrors:runtimeErrors.length});
  const result = {schemaVersion: 1, scope: 'CONTROLLED_NATIVE_MODEL_CONTRACT_NOT_PRODUCT_ACCEPTANCE', status: failures.length || checks.length !== requiredIds.length ? 'NATIVE_MODEL_CONTRACT_FAILED' : 'NATIVE_MODEL_CONTRACT_PASSED', checks, failures, blocked, runtimeErrors};
  writeFileSync(out + `/result-${Date.now()}.json`, JSON.stringify(result, null, 2) + '\n');console.log(JSON.stringify(result));
  if (failures.length) process.exitCode = 1;
}
