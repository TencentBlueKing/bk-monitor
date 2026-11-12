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
import {readFileSync, mkdirSync, writeFileSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
import assert from 'node:assert/strict';
import {waitForUiIdle} from './ui-snapshot.mjs';
const require = createRequire(new URL('../../packages/web-v3/package.json', import.meta.url));
const {chromium, expect} = require('@playwright/test');
const requested = process.argv[2];
if (!requested || new URL(requested).hostname !== 'appdev.woa.com') throw new Error('DEV_HOST_REQUIRED');
const target = new URL('/__fixtures__/collection-label-contract', requested).href;
const tracked = ['src/platform/compat/tdesign/runtime-contract.ts', 'src/platform/compat/vue3-component-model.ts', 'src/shared/ui/user-selector/index.tsx', 'src/features/clusters/current/cluster-manage/es-slider.tsx', 'src/features/clusters/current/cluster-manage/es-dialog.tsx', 'fixtures/collection-label-contract.tsx', 'fixtures/collection-label-contract.html', 'src/features/collection/current/components/common-comp/tag-more.tsx', 'src/features/collection/current/components/common-comp/tag-more.scss', 'src/features/collection/current/components/common-comp/use-label-picker-keyboard.ts', 'src/shared/composables/use-visible-input-focus.ts', 'src/features/collection/current/components/list-main/stop-type-dialog.tsx', 'src/features/collection/current/components/business-comp/step2/add-index-set.tsx', 'src/shared/ui/empty-status/index.vue', 'src/shared/ui/empty-status/types.ts', ...['403','404','500','building','empty','search-empty','login'].map(type=>'src/shared/assets/exception/'+type+'.svg')];
const sourceDigests = () => tracked.map(path => ({path, sha256: createHash('sha256').update(readFileSync(new URL('../../packages/web-v3/' + path, import.meta.url))).digest('hex')}));
const initial = sourceDigests(), checks = [], failures = [], blocked = [], runtimeErrors = [];
const required = ['label-render-nonbuiltin', 'label-required-cancel', 'label-duplicate-validation', 'label-builtin-validation', 'label-create-enter', 'label-disabled-add-delete', 'label-keyboard-cycle', 'label-search-enter', 'label-empty-enter', 'label-terminated', 'stop-dialog-single-cancel', 'stop-dialog-update-order', 'index-group-enter-create', 'index-group-enter-rename', 'index-group-invalid-enter', 'empty-original-assets-scenes', 'empty-clear-filter-operation', 'empty-refresh-operation', 'empty-slot-operation-override', 'empty-hide-title', 'cluster-nodes-hot-filter', 'cluster-nodes-warm-strict-value', 'cluster-nodes-empty-close','cluster-create-required-no-connect','cluster-create-pristine-close','cluster-create-dirty-close-guard','cluster-connect-resets-after-edit','cluster-management-native-controls','cluster-retention-custom-day-validation'];
const browser = await chromium.launch({headless: true, executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
let page;
try {
 const context = await browser.newContext({viewport: {width: 1440, height: 900}, locale: 'zh-CN', serviceWorkers: 'block'});
 await context.route('**/*', async route => {
  const request = route.request(), url = new URL(request.url());
  if (url.origin !== new URL(target).origin || request.method() !== 'GET' || ['xhr', 'fetch', 'ping'].includes(request.resourceType()) || url.pathname.startsWith('/api/')) {
   blocked.push({method: request.method(), path: url.pathname});await route.abort('blockedbyclient');
  } else await route.continue();
 });
 page = await context.newPage();page.setDefaultTimeout(8000);page.on('pageerror', error => runtimeErrors.push(error.message.slice(0, 500)));
 await page.goto(target, {waitUntil: 'domcontentloaded', timeout: 60000});
 await expect(page.getByRole('heading', {name: '采集标签组件契约（隔离接口）', exact: true})).toBeVisible({timeout: 20000});
 const cell = page.getByTestId('label-cell'), extension = page.locator('.new-label-container:visible');
 const search = page.locator('.collection-label-search input:visible');
 const calls = async () => JSON.parse(await page.getByTestId('label-calls').textContent());
 const reset = async () => {
  await page.getByRole('button', {name: '重置标签夹具', exact: true}).click();
  await expect(extension).toHaveCount(0);await expect(page.getByTestId('label-calls')).toHaveText('[]');
 };
 const open = async () => {await cell.getByRole('combobox').click();await expect(extension).toHaveCount(1);await expect(search).toBeFocused();};
 const draft = async value => {await open();await extension.locator('.add-new-label').click();const input = extension.locator('.new-label-input input');await input.fill(value);return input;};
 const error = async message => {await extension.locator('.operate-button .icon-check-line').click();const icon = extension.locator('.tooltips-icon');await expect(icon).toHaveCount(1);await icon.hover();await expect(page.getByText(message, {exact: true}).filter({visible: true})).toHaveCount(1);assert.deepEqual(await calls(), []);};
 const check = async (id, run) => {if(process.env.BKLOG_CONTRACT_CASE && process.env.BKLOG_CONTRACT_CASE!==id)return;try {await reset();await run();checks.push({id, passed: true});}catch(error){checks.push({id, passed: false});failures.push({id, reason: error.message.slice(0, 700)});console.log(JSON.stringify({diagnostic:'CASE_FAILED',id,reason:error.message.slice(0,700)}));}};
 await check('label-render-nonbuiltin', async () => {await expect(cell).toContainText('已有标签');await expect(cell).not.toContainText('内置标签');});
 await check('label-required-cancel', async () => {
  await draft('');await error('必填项');
  for (let round = 0; round < 2; round++) {
   await extension.locator('.operate-button .icon-close-line-2').click();
   await expect(extension.locator('.new-label-input')).toHaveCount(0);
   await waitForUiIdle(extension.locator('.add-new-label'));
   await expect(extension.locator('.new-label-input')).toHaveCount(0);assert.deepEqual(await calls(), []);
   if (round === 0) await extension.locator('.add-new-label').click();
  }
 });
 await check('label-duplicate-validation', async () => {await draft(' 已有标签 ');await error('已有同名标签');});
 await check('label-builtin-validation', async () => {await draft('内置标签');await error('内置标签名，请重新填写');});
 await check('label-create-enter', async () => {
  const input = await draft(' 新建标签 ');await input.press('Enter');
  await expect.poll(calls).toEqual([{method:'create',options:{data:{name:'新建标签',space_uid:'fixture-space'}}},{method:'add',options:{params:{index_set_id:'fixture-index'},data:{tag_id:4}}}]);
  await expect(cell).toContainText('新建标签');await expect(extension).toHaveCount(0);
 });
 await check('label-disabled-add-delete', async () => {
  await open();const selected = page.locator('.collection-label-picker .t-select-option').filter({hasText:'已有标签'});
  await expect(selected).toHaveClass(/t-is-disabled/);await selected.click();assert.deepEqual(await calls(), []);
  await page.locator('.collection-label-picker .t-select-option').filter({hasText:'可选标签'}).click();
  await expect(cell).toContainText('可选标签');
  const tag = cell.locator('.tag-item-label').filter({hasText:'可选标签'});await tag.hover();await tag.locator('.tag-item-close').click();
  await expect(cell).not.toContainText('可选标签');
  assert.deepEqual(await calls(), [{method:'add',options:{params:{index_set_id:'fixture-index'},data:{tag_id:2}}},{method:'delete',options:{params:{index_set_id:'fixture-index'},data:{tag_id:2}}}]);
 });
 await check('label-keyboard-cycle', async () => {
  const trigger = cell.getByRole('combobox');await trigger.focus();await trigger.press('Enter');await expect(search).toBeFocused();
  await search.press('ArrowDown');await page.keyboard.press('Enter');
  await expect.poll(calls).toEqual([{method:'add',options:{params:{index_set_id:'fixture-index'},data:{tag_id:2}}}]);
  await expect(cell).toContainText('可选标签');
 });
 await check('label-search-enter', async () => {
  await open();await search.fill('可选标签');await search.press('Enter');
  await expect.poll(calls).toEqual([{method:'add',options:{params:{index_set_id:'fixture-index'},data:{tag_id:2}}}]);
 });
 await check('label-empty-enter', async () => {
  const input=await draft('');await input.press('Enter');
  await expect(extension.locator('.new-label-input')).toHaveCount(1);assert.deepEqual(await calls(),[]);
 });
 await check('label-terminated', async () => {
  await page.getByRole('button', {name: '切换停用状态', exact: true}).click();
  await expect(cell.getByRole('combobox')).toHaveAttribute('tabindex', '-1');await cell.click();
  await expect(extension).toHaveCount(0);assert.deepEqual(await calls(), []);
 });
 await check('stop-dialog-single-cancel', async () => {
  await page.getByRole('button',{name:'打开停用预览',exact:true}).click();
  const dialog = page.locator('.stop-type-dialog');await expect(dialog).toContainText('请确认停用类型');
  await dialog.getByRole('button',{name:'取消',exact:true}).click();
  await expect(page.getByTestId('stop-events')).toHaveText('[{"event":"cancel","value":false}]');
  await page.getByRole('button',{name:'打开停用预览',exact:true}).click();await page.keyboard.press('Escape');
  await expect(page.getByTestId('stop-events')).toHaveText('[{"event":"cancel","value":false}]');
 });
 await check('stop-dialog-update-order', async () => {
  await page.getByRole('button',{name:'打开停用预览',exact:true}).click();
  const dialog = page.locator('.stop-type-dialog');await dialog.getByText('停用采集配置',{exact:true}).click();
  await dialog.getByRole('button',{name:'下一步',exact:true}).click();
  await expect(page.getByTestId('stop-events')).toHaveText('[{"event":"update","value":false},{"event":"cancel","value":false}]');
  assert.deepEqual(await calls(), []);
 });
 await check('index-group-enter-create', async () => {
  await page.getByRole('button',{name:'打开索引集新增',exact:true}).click();
  const editor=page.getByTestId('index-group-editor'), input=editor.getByPlaceholder('请输入',{exact:true});
  await input.fill('新索引集');await input.press('Enter');
  await expect.poll(calls).toEqual([{method:'group-create',options:{data:{space_uid:'fixture-space',index_set_name:'新索引集'}}}]);
  await expect(page.getByTestId('group-events')).toHaveText('[{"event":"submit","value":{"index_set_name":"新索引集"}}]');
  await expect(page.getByTestId('group-bubbles')).toHaveText('0');await expect(editor).toHaveCount(0);
 });
 await check('index-group-enter-rename', async () => {
  await page.getByRole('button',{name:'打开索引集重命名',exact:true}).click();
  const editor=page.getByTestId('index-group-editor'), input=editor.getByPlaceholder('请输入',{exact:true});
  await expect(input).toHaveValue('旧索引集');await input.fill('重命名索引集');await input.press('Enter');
  await expect.poll(calls).toEqual([{method:'group-update',options:{params:{index_set_id:'fixture-group'},data:{index_set_name:'重命名索引集'}}}]);
  await expect(page.getByTestId('group-bubbles')).toHaveText('0');await expect(editor).toHaveCount(0);
 });
 await check('index-group-invalid-enter', async () => {
  await page.getByRole('button',{name:'打开索引集新增',exact:true}).click();
  const editor=page.getByTestId('index-group-editor');await editor.getByPlaceholder('请输入',{exact:true}).press('Enter');
  await expect(editor.getByText('请输入索引集名称',{exact:true})).toBeVisible();
  assert.deepEqual(await calls(),[]);await expect(page.getByTestId('group-bubbles')).toHaveText('0');
  await editor.getByRole('button',{name:'取消',exact:true}).click();
 });
 await check('cluster-create-required-no-connect', async () => {
  await page.getByRole('button',{name:'Open cluster create',exact:true}).click();
  const drawer=page.locator('.bklog-cluster-drawer > .t-drawer__content-wrapper');await expect(drawer).toBeVisible();
  await expect(drawer.getByText('新建集群',{exact:true})).toBeVisible();
  await expect(drawer.locator('[data-test-id="esAccessFromBox_button_confirm"]')).toBeDisabled();
  await drawer.locator('[data-test-id="esAccessFromBox_button_connectivityTest"]').click();
  for (const label of ['集群名称','集群英文名称','来源','ES地址','端口']) await expect(drawer.getByText(label+'必填',{exact:true})).toBeVisible();
  assert.deepEqual(await calls(),[{method:'property-read',options:null}]);
  await drawer.locator('[data-test-id="esAccessFromBox_button_cancel"]').click();
  await expect(drawer).not.toBeVisible();
 });
 await check('cluster-create-pristine-close', async () => {
  await page.getByRole('button',{name:'Open cluster create',exact:true}).click();
  const drawer=page.locator('.bklog-cluster-drawer > .t-drawer__content-wrapper');await expect(drawer).toBeVisible();
  await expect.poll(calls).toEqual([{method:'property-read',options:null}]);
  await drawer.locator('[data-test-id="esAccessFromBox_button_cancel"]').click();
  await expect(page.getByTestId('cluster-slider-events')).toHaveText('["cancel"]');await expect(drawer).not.toBeVisible();
 });
 await check('cluster-create-dirty-close-guard', async () => {
  await page.getByRole('button',{name:'Open cluster create',exact:true}).click();
  const drawer=page.locator('.bklog-cluster-drawer > .t-drawer__content-wrapper');await expect(drawer).toBeVisible();
  await expect.poll(calls).toEqual([{method:'property-read',options:null}]);
  await drawer.locator('[data-test-id="esAccessFromBox_input_fillName"] input').fill('fixture draft');
  await drawer.locator('[data-test-id="esAccessFromBox_button_cancel"]').click();
  const guard=page.locator('.sideslider-close-cls');await expect(guard).toBeVisible();
  await guard.getByRole('button',{name:'取消',exact:true}).click();
  await expect(drawer).toBeVisible();await expect(drawer.locator('[data-test-id="esAccessFromBox_input_fillName"] input')).toHaveValue('fixture draft');
  await drawer.locator('[data-test-id="esAccessFromBox_button_cancel"]').click();
  await guard.getByRole('button',{name:'离开',exact:true}).click();
  await expect(page.getByTestId('cluster-slider-events')).toHaveText('["cancel"]');
  await expect(drawer).not.toBeVisible();
  await page.getByRole('button',{name:'Open cluster create',exact:true}).click();
  await expect(drawer.locator('[data-test-id="esAccessFromBox_input_fillName"] input')).toHaveValue('');
  assert.ok((await calls()).every(call=>call.method==='property-read'));
  await drawer.locator('[data-test-id="esAccessFromBox_button_cancel"]').click();
  await expect(drawer).not.toBeVisible();
 });
 const openConnectedCluster = async () => {
  await page.getByRole('button',{name:'Open cluster create',exact:true}).click();
  const drawer=page.locator('.bklog-cluster-drawer > .t-drawer__content-wrapper');await expect(drawer).toBeVisible();
  await drawer.locator('[data-test-id="esAccessFromBox_input_fillName"] input').fill('fixture cluster');
  await drawer.getByPlaceholder('支持字母、数字、下划线、连字符',{exact:true}).fill('fixture-cluster');
  await drawer.locator('.source-item .t-select').click();
  await page.locator('.t-select-option:visible').filter({hasText:'Other'}).click();
  await drawer.locator('[data-test-id="esAccessFromBox_input_fillDomainName"] input').fill('es.example.invalid');
  const port=drawer.locator('.t-form__item').filter({has:page.getByText('端口',{exact:true})}).locator('input');await port.fill('9200');await port.press('Tab');
  await drawer.locator('[data-test-id="esAccessFromBox_button_connectivityTest"]').click();
  await expect.poll(async()=> (await calls()).map(call=>call.method)).toEqual(['property-read','connectivity-read','node-attrs-read']);
  const records=await calls(), expected={bk_biz_id:5000140,cluster_name:'fixture-cluster',display_name:'fixture cluster',domain_name:'es.example.invalid',port:'9200',schema:'http',es_auth_info:{username:'',password:''}};
  assert.deepEqual(records[1].options,{data:expected});assert.deepEqual(records[2].options,{data:expected});
  await expect(drawer.locator('[data-test-id="esAccessFromBox_button_confirm"]')).toBeEnabled();
  return drawer;
 };
 const closeChangedCluster = async drawer => {
  await drawer.locator('[data-test-id="esAccessFromBox_button_cancel"]').click();
  await page.locator('.sideslider-close-cls').getByRole('button',{name:'离开',exact:true}).click();
  await expect(drawer).not.toBeVisible();
 };
 await check('cluster-connect-resets-after-edit', async () => {
  const drawer=await openConnectedCluster();
  await drawer.locator('[data-test-id="esAccessFromBox_input_fillDomainName"] input').fill('changed.example.invalid');
  await expect(drawer.locator('[data-test-id="esAccessFromBox_button_confirm"]')).toBeDisabled();
  await closeChangedCluster(drawer);
 });
 await check('cluster-management-native-controls', async () => {
  const drawer=await openConnectedCluster();await drawer.getByText('ES集群管理',{exact:true}).click();
  const replicas=drawer.locator('.t-form__item').filter({has:page.getByText('副本数',{exact:true})}).locator('input');
  await expect(replicas).toHaveCount(2);await expect(replicas.nth(0)).toHaveValue('1');await expect(replicas.nth(1)).toHaveValue('3');
  await replicas.nth(0).fill('2');await replicas.nth(0).press('Tab');await expect(replicas.nth(0)).toHaveValue('2');
  const shards=drawer.locator('.t-form__item').filter({has:page.getByText('分片数',{exact:true})}).locator('input');
  await expect(shards).toHaveCount(2);await expect(shards.nth(0)).toHaveValue('3');await expect(shards.nth(1)).toHaveValue('3');
  const hot=drawer.locator('.t-form__item').filter({has:page.getByText('冷热数据',{exact:true})}).locator('.t-switch');await expect(hot).toHaveCount(1);await hot.click();
  await expect(shards.nth(0)).toHaveValue('2');await expect(shards.nth(1)).toHaveValue('2');
  await expect(drawer.locator('[data-test-id="esAccessFromBox_button_confirm"]')).toBeDisabled();
  const group=label=>drawer.locator('.form-item-container .bk-form-item').filter({has:page.getByText(label,{exact:true})});
  await group('热数据标签').locator('.t-select').click();
  await page.locator('.cluster-hot-node-options .t-select-option:visible').filter({hasText:'tier:hot(1)'}).click();
  await group('冷数据标签').locator('.t-select').click();
  await expect(page.locator('.cluster-cold-node-options .t-select-option:visible').filter({hasText:'tier:hot(1)'})).toHaveClass(/t-is-disabled/);
  await page.locator('.cluster-cold-node-options .t-select-option:visible').filter({hasText:'tier:cold(2)'}).click();
  await expect(drawer.locator('[data-test-id="esAccessFromBox_button_confirm"]')).toBeEnabled();
  const description=drawer.locator('textarea');await expect(description).toHaveCount(1);await description.fill('fixture description');await expect(description).toHaveValue('fixture description');
  await closeChangedCluster(drawer);
 });
 await check('cluster-retention-custom-day-validation', async () => {
  const drawer=await openConnectedCluster();await drawer.getByText('ES集群管理',{exact:true}).click();
  const selects=drawer.locator('[data-test-id="storageBox_select_selectExpiration"]');await expect(selects).toHaveCount(2);
  await expect(selects.nth(0)).toContainText('7天');await expect(selects.nth(1)).toContainText('14天');
  await selects.nth(1).click();
  const maxPanel=page.locator('.cluster-retention-max-options'), customMax=maxPanel.getByPlaceholder('输入自定义天数，按 Enter 确认',{exact:true});
  await customMax.fill('5');await customMax.press('Enter');
  await expect(page.getByText('默认天数不能大于最大天数',{exact:true})).toBeVisible();
  await expect(selects.nth(1)).toContainText('14天');await expect(customMax).toHaveValue('5');
  await customMax.fill('21');await customMax.press('Enter');await expect(selects.nth(1)).toContainText('21天');
  await expect(customMax).not.toBeVisible();
  await expect(page.getByText('默认天数不能大于最大天数',{exact:true})).toHaveCount(0,{timeout:8000});
  await selects.nth(0).click();
  const defaultPanel=page.locator('.cluster-retention-default-options'), custom=defaultPanel.getByPlaceholder('输入自定义天数，按 Enter 确认',{exact:true});
  await custom.fill('22');await custom.press('Enter');
  await expect(page.getByText('默认天数不能大于最大天数',{exact:true})).toBeVisible();await expect(selects.nth(0)).toContainText('7天');
  await custom.fill('0');await custom.press('Enter');await expect(page.getByText('请输入有效数值',{exact:true})).toBeVisible();await expect(custom).toHaveValue('');
  await custom.fill('10');await custom.press('Enter');await expect(selects.nth(0)).toContainText('10天');await expect(custom).not.toBeVisible();
  await selects.nth(1).click();await expect(maxPanel.locator('.t-select-option:visible').filter({hasText:/^7$/})).toHaveClass(/t-is-disabled/);
  await maxPanel.locator('.t-select-option:visible').filter({hasText:/^14$/}).click();await expect(selects.nth(1)).toContainText('14天');
  await closeChangedCluster(drawer);
 });
 await check('cluster-nodes-hot-filter', async () => {
  await page.getByRole('button',{name:'打开节点 hot',exact:true}).click();
  const dialog=page.locator('.bklog-cluster-nodes-dialog:visible');await expect(dialog).toBeVisible();
  await expect(dialog).toContainText('包含属性 tier:hot 的节点列表');
  await expect(dialog.locator('thead th')).toHaveText(['ID','Name','Host']);
  await expect(dialog.locator('tbody tr:not(.t-table__empty-row)')).toHaveCount(1);
  await expect(dialog).toContainText('node-hot');await expect(dialog).toContainText('192.0.2.1');
  await expect(dialog.locator('.t-dialog__footer')).toHaveCount(0);
  await dialog.locator('.t-dialog__close').click();await expect(page.getByTestId('node-events')).toHaveText('[false]');
 });
 await check('cluster-nodes-warm-strict-value', async () => {
  await page.getByRole('button',{name:'打开节点 warm',exact:true}).click();
  const dialog=page.locator('.bklog-cluster-nodes-dialog:visible');await expect(dialog).toContainText('包含属性 tier:1 的节点列表');
  await expect(dialog.locator('tbody tr:not(.t-table__empty-row)')).toHaveCount(1);
  await expect(dialog).toContainText('node-warm-number');await expect(dialog).not.toContainText('node-warm-string');
  await page.keyboard.press('Escape');await expect(page.getByTestId('node-events')).toHaveText('[false]');
 });
 await check('cluster-nodes-empty-close', async () => {
  await page.getByRole('button',{name:'打开节点 missing',exact:true}).click();
  const dialog=page.locator('.bklog-cluster-nodes-dialog:visible');await expect(dialog).toContainText('包含属性 tier:missing 的节点列表');
  await expect(dialog.locator('tbody tr:not(.t-table__empty-row)')).toHaveCount(0);
  await expect(dialog.locator('.t-table__empty')).toBeVisible();
  await page.mouse.click(20,20);await expect(page.getByTestId('node-events')).toHaveText('[false]');
  assert.deepEqual(await calls(),[]);
 });
 await check('empty-original-assets-scenes', async () => {
  const root=page.getByTestId('empty-component'), image=root.locator('img.exception-image');
  for (const type of ['empty','search-empty','500','403','404','building','login']) {
   await page.getByRole('button',{name:`切换空态 ${type}`,exact:true}).click();await expect(image).toHaveCount(1);
   await expect.poll(()=>image.evaluate(element=>element.complete&&element.naturalWidth>0)).toBe(true);
   assert.equal((await image.boundingBox()).height,100);assert.doesNotMatch(await image.getAttribute('src'),/8001|bk-magic-vue/);
  }
  await page.getByRole('button',{name:'切换空态尺寸',exact:true}).click();assert.equal((await image.boundingBox()).height,180);
  await page.getByRole('button',{name:'切换空态尺寸',exact:true}).click();
 });
 await check('empty-clear-filter-operation', async () => {
  await page.getByRole('button',{name:'切换空态 search-empty',exact:true}).click();const root=page.getByTestId('empty-component');
  await expect(root).toContainText('搜索结果为空');await expect(root).toContainText('可以尝试');
  await root.getByText('清空筛选条件',{exact:true}).click();await expect(page.getByTestId('empty-operations')).toHaveText('["clear-filter"]');
 });
 await check('empty-refresh-operation', async () => {
  await page.getByRole('button',{name:'切换空态 500',exact:true}).click();const root=page.getByTestId('empty-component');
  await expect(root).toContainText('数据获取异常');await root.getByText('刷新',{exact:true}).click();await expect(page.getByTestId('empty-operations')).toHaveText('["refresh"]');
 });
 await check('empty-slot-operation-override', async () => {
  await page.getByRole('button',{name:'切换空态 search-empty',exact:true}).click();await page.getByRole('button',{name:'切换空态插槽',exact:true}).click();
  await expect(page.getByTestId('empty-custom-state')).toHaveText('true');
  const root=page.getByTestId('empty-component');
  const slotDiagnostic=await root.evaluate(element=>{const component=element.querySelector('.empty-status-container').__vueParentComponent;return{file:component.type.__file,slotKeys:Object.keys(component.slots),legacySlotKeys:Object.keys(component.proxy.$slots),setupSlotKeys:Object.keys(component.setupState.slots??{}),vnodeChildKeys:Object.keys(component.vnode.children??{}),compatConfig:component.type.compatConfig};});
  console.log(JSON.stringify({diagnostic:'EMPTY_SLOT_BINDING_ONLY',...slotDiagnostic}));
  await expect(root).toContainText('自定义空态说明');await expect(root).toContainText('搜索结果为空');
  await expect(root.getByText('清空筛选条件',{exact:true})).toHaveCount(0);await page.getByRole('button',{name:'切换空态插槽',exact:true}).click();
 });
 await check('empty-hide-title', async () => {
  await page.getByRole('button',{name:'切换空态 empty',exact:true}).click();await page.getByRole('button',{name:'切换空态标题',exact:true}).click();
  const root=page.getByTestId('empty-component');await expect(root.locator('.empty-text')).toHaveCount(0);await expect(root.locator('img.exception-image')).toBeVisible();
  await page.getByRole('button',{name:'切换空态标题',exact:true}).click();
 });
} catch(error) {failures.push({id:'fixture-initialization',reason:error.message.slice(0, 700)});}
finally {
 if (JSON.stringify(initial) !== JSON.stringify(sourceDigests())) failures.push({id:'source-integrity',reason:'SOURCE_CHANGED_DURING_RUN'});
 if (blocked.length || runtimeErrors.length) failures.push({id:'isolated-boundary',reason:'UNEXPECTED_NETWORK_OR_RUNTIME_ERROR'});
 const missing = required.filter(id => checks.filter(check => check.id === id && check.passed).length !== 1);
 const out = fileURLToPath(new URL('../runs/calibration/collection-label/', import.meta.url));mkdirSync(out,{recursive:true});
 await page?.screenshot({path:out + `/screen-${Date.now()}.png`}).catch(()=>{});await browser.close();
 const result = {schemaVersion:1,scope:'CONTROLLED_REAL_COMPONENT_CONTRACT_NOT_BACKEND_ACCEPTANCE',status:failures.length || missing.length?'LABEL_CONTRACT_FAILED':'LABEL_CONTRACT_PASSED',checks,missing,failures,blocked,runtimeErrors,sourceDigests:initial};
 writeFileSync(out + `/result-${Date.now()}.json`,JSON.stringify(result,null,2)+'\n');console.log(JSON.stringify(result));if(failures.length || missing.length)process.exitCode=1;
}
