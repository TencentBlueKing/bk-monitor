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
import {writeFileSync} from 'node:fs';
import {resolve} from 'node:path';
import {captureUi} from './ui-snapshot.mjs';
const require = createRequire(new URL('../../packages/web-v3/package.json', import.meta.url));
const {expect} = require('@playwright/test');

/** One source-derived recipe shared by live capture and isolated self-replay. */
export async function runRetrieveRowPilot(page, {entries, privateDir, readBody, setPhase = () => {}, checkpoints, expectedContext, readRequest}) {
  await expect.poll(() => entries.some(e => e.path === '/api/v1/search/index_set/16176/search/' && e.complete), {timeout: 60000}).toBe(true);
  await expect.poll(() => entries.filter(e => e.policy.decision === 'ALLOW' && !e.complete && !e.failure && !e.captureError).length, {timeout: 60000}).toBe(0);
  const hash = new URL(page.url()).hash.slice(1);
  const [path, query] = hash.split('?');
  if (path !== `/retrieve/${expectedContext.indexId}`) throw new Error('WRONG_RETRIEVE_ROUTE');
  const params = new URLSearchParams(query);
  for (const key of ['spaceUid', 'bizId', 'start_time', 'end_time']) {
    if (params.get(key) !== String(expectedContext[key])) throw new Error('URL_CONTEXT_MISMATCH:' + key);
  }
  const queryRecord = entries.find(e => e.path === '/api/v1/search/index_set/16176/search/' && e.complete);
  const request = readRequest(queryRecord);
  const body = JSON.parse(request.body);
  for (const [key, expected] of Object.entries({start_time: expectedContext.start_time, end_time: expectedContext.end_time, time_zone: expectedContext.timezone, bk_biz_id: expectedContext.bizId, search_mode: 'ui'})) {
    if (body[key] !== expected) throw new Error('REQUEST_CONTEXT_MISMATCH:' + key);
  }
  if (await page.evaluate(() => Date.now()) !== expectedContext.clockEpochMs) throw new Error('CLOCK_CONTEXT_MISMATCH');
  if (expectedContext.capabilities?.includes('advancing-clock-after-bootstrap')) await page.clock.setSystemTime(expectedContext.clockEpochMs + 1);
  const row = page.locator('.bklog-row-container[data-row-index="0"]');
  await expect(row).toHaveCount(1, {timeout: 20000});
  await expect(row.locator('.bklog-expand-icon')).toBeVisible();
  async function checkpoint(id, extraBindings = []) {
    await page.screenshot({path: resolve(privateDir, `${id}.png`)});
    if (id === 'query-ready') {
      const selectedFields = await page.locator('.fields-container.is-selected .filed-title .field-name').allTextContents();
      writeFileSync(resolve(privateDir, 'query-ready.sidebar.json'), JSON.stringify({schemaVersion: 1, fieldNames: selectedFields.map(name => name.trim())}, null, 2), {mode: 0o600});
    }
    const rowSelector = '.bklog-row-container[data-row-index="0"]';
    const bindings = [{semanticId: 'result.row.fixture-index0.expand', selector: `${rowSelector} .bklog-expand-icon`}, ...extraBindings];
    if (await row.locator('.expand-view-wrapper').count()) {
      bindings.push({semanticId: 'result.row.expand.tabs', selector: `${rowSelector} .expand-view-wrapper .tab-left`});
      if (await row.locator('.expand-view-wrapper input[placeholder="搜索字段"]').isVisible()) bindings.push({semanticId: 'result.row.expand.field-search', selector: `${rowSelector} .expand-view-wrapper input[placeholder="搜索字段"]`});
    }
    const ui = await page.evaluate(captureUi, {bindings});
    writeFileSync(resolve(privateDir, `${id}.ui.json`), JSON.stringify(ui, null, 2), {mode: 0o600});
    if (ui.errors.length) throw new Error(`CHECKPOINT_TARGET_INVALID:${id}`);
    checkpoints.push({id, route: new URL(page.url()).hash, rowCount: await page.locator('.bklog-row-container[data-row-index]').count(), capturedAt: Date.now()});
  }
  if (process.env.BKLOG_DEBUG_FIELDS === '1') {
    // Framework internals are diagnostic input only, never acceptance oracles.
    const debug = await page.evaluate(() => {
      const node = document.querySelector('.fields-container.is-selected .filed-list');
      const chain = [];
      for (let instance = node?.__vueParentComponent; instance; instance = instance.parent) {
        const proxy = instance.proxy;
        chain.push({name: instance.type?.name, compatConfig: instance.type?.compatConfig, props: Object.fromEntries(Object.entries(instance.props ?? {}).filter(([key]) => ['modelValue', 'value', 'list', 'visibleFields'].includes(key)).map(([key, value]) => [key, Array.isArray(value) ? {arrayLength: value.length} : typeof value])), dragVisibleFields: Array.isArray(proxy?.dragVisibleFields) ? proxy.dragVisibleFields.length : null, visibleFields: Array.isArray(proxy?.visibleFields) ? proxy.visibleFields.length : null, attrNames: Object.keys(instance.attrs ?? {})});
      }
      return {purpose: 'DEBUG_NOT_ACCEPTANCE_ORACLE', selectedFieldNodes: document.querySelectorAll('.fields-container.is-selected .filed-item').length, chain};
    });
    writeFileSync(resolve(privateDir, 'field-render-debug.json'), JSON.stringify(debug, null, 2), {mode: 0o600});
  }
  await checkpoint('query-ready');
  if (expectedContext.capabilities?.includes('selected-field-search-restore')) {
    setPhase('sidebar-field-search');
    const requestsBefore=entries.length, sidebar=page.locator('.field-filter-box');
    const search=sidebar.getByPlaceholder('搜索 字段名',{exact:true});await expect(search).toHaveCount(1);
    const selected=page.locator('.fields-container.is-selected .filed-title .field-name');
    const names=(await selected.allTextContents()).map(value=>value.trim());
    const searchBinding={semanticId:'retrieval.sidebar.field-search',selector:'.field-filter-box .form-container .king-input'};
    await search.fill('level');
    await expect.poll(async()=> (await page.locator('.fields-container.is-selected .filed-title .field-name:visible').allTextContents()).map(value=>value.trim())).toEqual(['level']);
    await checkpoint('sidebar-field-filter',[searchBinding]);
    await search.fill('__migration_missing_sidebar_field__');
    await expect(page.locator('.fields-container.is-selected .filed-title .field-name:visible')).toHaveCount(0);
    await expect(sidebar.getByText('显示字段',{exact:true})).toBeVisible();
    await expect(sidebar.locator('.empty-status-container')).toHaveCount(0);
    await checkpoint('sidebar-field-no-match',[searchBinding]);
    await search.hover();
    const clear=sidebar.locator('.form-container .clear-icon, .form-container .t-input__suffix-clear');await expect(clear).toHaveCount(1);await clear.click();
    await expect(search).toHaveValue('');
    await expect.poll(async()=> (await selected.allTextContents()).map(value=>value.trim())).toEqual(names);
    await expect(sidebar.locator('.empty-status-container')).toHaveCount(0);
    if(entries.length!==requestsBefore)throw new Error('SIDEBAR_LOCAL_SEARCH_OBSERVATION_REQUEST_CHANGED');
    await checkpoint('sidebar-field-restored',[searchBinding]);
  }
  setPhase('expand-row');
  await row.locator('.bklog-expand-icon').click();
  const panel = row.locator('.expand-view-wrapper');
  await expect(panel).toBeVisible();
  const fields = panel.locator('.field-text');
  await expect.poll(() => fields.count()).toBeGreaterThan(1);
  const originalFields = await fields.allTextContents();
  if (!originalFields.some(field => field === 'level')) throw new Error('FIXTURE_REQUIRES_LEVEL_FIELD');
  const search = panel.getByPlaceholder('搜索字段', {exact: true});
  await expect(search).toHaveCount(1);
  setPhase('filter-existing-panel');
  await search.fill('level');
  await search.press('Enter');
  await expect.poll(() => fields.allTextContents()).toEqual(['level']);
  const searchEntry = entries.find(e => e.path === '/api/v1/search/index_set/16176/search/' && e.complete);
  const events = readBody(searchEntry).trim().split('\n').map(line => JSON.parse(line));
  const firstRow = events.find(event => event.event === 'row' && event.index === 0);
  const level = (firstRow?.origin_data ?? firstRow?.data)?.level;
  if (typeof level !== 'string') throw new Error('SOURCE_DATA_ROW_IDENTITY_UNRESOLVED');
  await expect(panel.locator('.kv-view-content .field-value[data-field-name="level"]')).toHaveText(level);
  await checkpoint('expanded-kv-filter');
  if (expectedContext.capabilities?.includes('row-field-search-icons')) {
    const requestsBefore = entries.length;
    setPhase('field-search-icons');
    // V2 commits nonempty drafts only on Enter/right-icon-click, never on typing.
    await search.fill('__migration_no_matching_field__');
    await expect.poll(() => fields.allTextContents()).toEqual(['level']);
    const submit = panel.locator('.input-right-icon.icon-search, button.field-search-submit');
    await expect(submit).toHaveCount(1);
    await submit.click();
    await expect(fields).toHaveCount(0);
    await checkpoint('expanded-no-match');
    await search.hover();
    const clear = panel.locator('.clear-icon, .t-input__suffix-clear');
    await expect(clear).toHaveCount(1);
    await clear.click();
    await expect(search).toHaveValue('');
    await expect.poll(() => fields.allTextContents()).toEqual(originalFields);
    await checkpoint('expanded-clear-restored');
    await search.fill('  level  ');
    await submit.click();
    await expect.poll(() => fields.allTextContents()).toEqual(['level']);
    await expect(search).toHaveValue('  level  ');
    // Whitespace-only input resets immediately, as handleInputChange does in V2.
    await search.fill('   ');
    await expect.poll(() => fields.allTextContents()).toEqual(originalFields);
    await search.fill('level');
    await submit.click();
    await expect.poll(() => fields.allTextContents()).toEqual(['level']);
    if (entries.length !== requestsBefore) throw new Error('LOCAL_FIELD_SEARCH_ISSUED_REQUEST');
  }
  setPhase('switch-json');
  await panel.locator('.tab-left').getByText('JSON', {exact: true}).click();
  await expect(panel.locator('.json-view-content')).toBeVisible();
  await expect(panel.locator('.tab-left .activeJson')).toHaveText('JSON');
  await checkpoint('expanded-json');
  if (expectedContext.capabilities?.includes('row-copy-payload-native-event')) {
    setPhase('copy-origin-row');
    const requestsBefore = entries.length;
    await page.evaluate(() => {
      window.__migrationCopyEvents = [];
      window.__migrationCopyListener = event => {
        const element = document.activeElement;
        const isTextArea = element instanceof HTMLTextAreaElement;
        window.__migrationCopyEvents.push({trusted:event.isTrusted,prevented:event.defaultPrevented,source:isTextArea?'ACTIVE_TEXTAREA':'UNRESOLVED',text:isTextArea?element.value.slice(element.selectionStart,element.selectionEnd):null});
      };
      window.addEventListener('copy',window.__migrationCopyListener);
    });
    let records;
    try {
      const copy = panel.locator('.tab-right .bklog-data-copy');await expect(copy).toHaveCount(1);await copy.click();
      await expect(page.getByText('复制成功',{exact:true})).toBeVisible();
      records = await page.evaluate(() => window.__migrationCopyEvents);
    } finally {
      await page.evaluate(() => {window.removeEventListener('copy',window.__migrationCopyListener);delete window.__migrationCopyListener;delete window.__migrationCopyEvents;});
    }
    if (records.length !== 1 || !records[0].trusted || records[0].prevented || records[0].source !== 'ACTIVE_TEXTAREA') throw new Error('COPY_NATIVE_EVENT_NOT_PROVEN');
    let payload;
    try {payload = JSON.parse(records[0].text);} catch {throw new Error('COPY_PAYLOAD_NOT_JSON');}
    const original = firstRow.origin_data ?? firstRow.data;
    for (const key of ['level','log','dtEventTimeStamp']) {
      if (!Object.hasOwn(payload,key) || payload[key] !== original[key]) throw new Error('COPY_FIELD_VALUE_MISMATCH:' + key);
    }
    writeFileSync(resolve(privateDir,'expanded-copy-payload.clipboard.json'),JSON.stringify({schemaVersion:1,source:'TRUSTED_NATIVE_COPY_EVENT_ACTIVE_TEXTAREA',osClipboardReadback:false,payload},null,2),{mode:0o600});
    await page.mouse.move(1000,80);
    if (entries.length !== requestsBefore) throw new Error('COPY_OBSERVATION_WINDOW_REQUEST_COUNT_CHANGED');
    await checkpoint('expanded-copy-payload');
  }
  setPhase('restore-and-collapse');
  await panel.locator('.tab-left').getByText('KV', {exact: true}).click();
  await expect(panel.locator('.kv-view-content')).toBeVisible();
  await expect(search).toHaveValue('level');
  await search.fill('');
  await expect.poll(() => fields.allTextContents()).toEqual(originalFields);
  await row.locator('.bklog-expand-icon').click();
  await expect(panel).toHaveCount(0);
  await checkpoint('collapsed-restored');
}
