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
import {captureUi, waitForUiIdle} from './ui-snapshot.mjs';
const require = createRequire(new URL('../../packages/web-v3/package.json', import.meta.url));
const {expect} = require('@playwright/test');

/** Open and cancel only. Never click Next/Confirm on an existing collector. */
export async function runManagementMenuPilot(page, {entries, privateDir, readBody, checkpoints, setPhase = () => {}, labelPreview = false, labelCancelPreview = false, navClusterPreview = false, clusterSearchPreview = false, readRequest}) {
  await expect.poll(() => entries.some(e => e.path === '/api/v1/databus/log_access/collector/' && e.complete), {timeout: 60000}).toBe(true);
  await expect.poll(() => entries.filter(e => e.policy.decision === 'ALLOW' && !e.complete && !e.failure && !e.captureError).length, {timeout: 60000}).toBe(0);
  const hash = new URL(page.url()).hash;
  if (!hash.startsWith('#/manage/log-collection/collection-item/list?')) throw new Error('WRONG_MANAGEMENT_ROUTE');
  const query = new URLSearchParams(hash.split('?')[1]);
  if (query.get('bizId') !== '5000140' || query.get('spaceUid') !== 'bkcc__5000140') throw new Error('WRONG_MANAGEMENT_CONTEXT');
  const listEntry = entries.find(e => e.path === '/api/v1/databus/log_access/collector/' && e.complete);
  const response = JSON.parse(readBody(listEntry));
  const candidates = response.data.list.filter(row => row.log_access_type === 'linux' && !row.is_related_space);
  if (!candidates.length) throw new Error('FIXTURE_REQUIRES_LINUX_ROW');
  const data = candidates[0], name = data.collector_config_name || data.name;
  const row = page.locator('.t-table tbody tr').filter({has: page.getByText(name, {exact: true})});
  await expect(row).toHaveCount(1);
  await expect(row).toContainText(String(data.bk_data_id));
  const trigger = row.locator('.table-more-btn');await expect(trigger).toHaveCount(1);
  const initialRows = await page.locator('.t-table tbody tr').count();
  async function checkpoint(id, bindings = []) {
    const ui = await page.evaluate(captureUi, {bindings});
    if (ui.errors.length) throw new Error('MANAGEMENT_CHECKPOINT_TARGET_INVALID:' + id);
    await page.screenshot({path: resolve(privateDir, id + '.png')});
    writeFileSync(resolve(privateDir, id + '.ui.json'), JSON.stringify(ui, null, 2), {mode: 0o600});
    checkpoints.push({id, route: new URL(page.url()).hash, rowId: data.collector_config_id, dataId: data.bk_data_id});
  }
  await checkpoint('list-ready');
  setPhase('menu-open');await trigger.click();
  const menu = page.locator('.row-menu-content:visible');await expect(menu).toHaveCount(1);
  const labels = await menu.locator('.menu-item').allTextContents();
  writeFileSync(resolve(privateDir, 'menu-items.json'), JSON.stringify({labels: labels.map(label => label.trim())}), {mode: 0o600});
  const stop = menu.getByText('停用', {exact: true});await expect(stop).toHaveCount(1);await expect(stop).not.toHaveClass(/disabled/);
  await checkpoint('menu-open', [{semanticId: 'collection.row.more-menu', selector: '.row-menu-content'}]);
  setPhase('stop-type-preview');await stop.click();
  const dialog = page.locator('.stop-type-dialog:visible');await expect(dialog).toHaveCount(1);
  await expect(dialog).toContainText('请确认停用类型');
  // Wait for the actual menu close transition; a hidden Tippy can remain mounted.
  await expect(menu).toHaveCount(0);
  const choice = dialog.locator('.type-item').filter({has: page.getByText('停用采集配置', {exact: true})});
  await choice.click();await expect(choice).toHaveClass(/active/);
  // Diagnostic only: wrapper DOM differs between libraries and is not an oracle.
  const layout = await page.evaluate(() => {
    const chain = [];
    for (let node = document.querySelector('.stop-type-dialog-content'); node; node = node.parentElement) {
      const rect = node.getBoundingClientRect(), style = getComputedStyle(node);
      chain.push({tag: node.tagName, class: node.className, role: node.getAttribute('role'), rect: {x: rect.x, y: rect.y, width: rect.width, height: rect.height}, padding: style.padding, overflow: style.overflow, margin: style.margin});
    }
    const row = document.querySelector('.t-table tbody tr');
    const menu = document.querySelector('.row-menu-content');
    const popper = menu?.closest('[data-tippy-root]');
    const components = [];
    for (let c = document.querySelector('.table-more-btn')?.__vueParentComponent; c; c = c.parent) {
      components.push({name: c.type?.name, exposedKeys: c.exposed && Object.keys(c.exposed), setupKeys: Object.keys(c.setupState ?? {}), refs: Object.fromEntries(Object.entries(c.refs ?? {}).map(([key, value]) => [key, {hasHide: typeof value?.hide, exposed: value?.$?.exposed && Object.keys(value.$.exposed)}]))});
      if (components.length === 5) break;
    }
    return {components, tippy: popper?._tippy?.state, chain, row: row && {class: row.className, parentClass: row.parentElement.className, height: row.getBoundingClientRect().height, style: row.getAttribute('style'), cells: [...row.cells].map(cell => ({components: [...cell.querySelectorAll('*')].slice(0, 8).map(n => {const c=n.__vueParentComponent;return {tag:n.tagName, class:n.className, name:c?.type?.name, slots:Object.keys(c?.slots??{}), attrs:Object.keys(c?.attrs??{})};}), descendants: [...cell.querySelectorAll('*')].filter(n => n.getBoundingClientRect().height >= 40).slice(0, 10).map(n => ({class: n.className, tag: n.tagName, height: n.getBoundingClientRect().height, lineHeight: getComputedStyle(n).lineHeight, padding: getComputedStyle(n).padding})), class: cell.className, height: cell.getBoundingClientRect().height, padding: getComputedStyle(cell).padding, lineHeight: getComputedStyle(cell).lineHeight}))}, visibleMenus: [...document.querySelectorAll('.row-menu-content')].filter(node => node.getBoundingClientRect().width && getComputedStyle(node).visibility !== 'hidden').length};
  });
  writeFileSync(resolve(privateDir, 'dialog-layout.debug.json'), JSON.stringify(layout, null, 2), {mode: 0o600});

  await checkpoint('stop-type-preview', [{semanticId: 'collection.stop-type.dialog', selector: '.stop-type-dialog .bk-dialog-content, .stop-type-dialog.t-dialog', nameSelector: '.bk-dialog-header-inner, .t-dialog__header-content'}, {semanticId: 'collection.stop-type.selected-choice', selector: '.stop-type-dialog .type-item.active'}]);
  setPhase('cancel-stop-preview');await dialog.getByRole('button', {name: '取消', exact: true}).click();
  await expect(dialog.getByText('请确认停用类型', {exact: true})).not.toBeVisible();
  await expect(dialog.locator('.stop-type-dialog-content')).not.toBeVisible();
  // BlueKing retains an empty transfer wrapper after close. Prove hit testing
  // and restored interaction instead of requiring the wrapper to disappear.
  await trigger.click();await expect(menu).toHaveCount(1);
  await menu.getByText('停用', {exact: true}).click();
  await expect(dialog.locator('.type-item.active')).toContainText('停用采集配置');
  await dialog.getByRole('button', {name: '取消', exact: true}).click();
  await expect(dialog.getByText('请确认停用类型', {exact: true})).not.toBeVisible();
  await expect(row).toHaveCount(1);await expect(page.locator('.t-table tbody tr')).toHaveCount(initialRows);
  const writes = entries.filter(e => e.policy.decision === 'BLOCK' && e.policy.reason !== 'EXCLUDED_TELEMETRY');
  if (writes.length) throw new Error('UNEXPECTED_MANAGEMENT_REQUEST_BLOCKED:' + writes.map(e => e.path).join(','));
  await checkpoint('cancel-restored-list');
  if (labelPreview) {
    const labelTrigger = row.locator('.tags-cell .tag-more-label-select-trigger');
    await expect(labelTrigger).toHaveCount(1);
    await page.evaluate(() => {
      window.__labelFocusEvents = [];
      window.__labelFocusListener = event => window.__labelFocusEvents.push({class: event.target.className, tag: event.target.tagName, placeholder: event.target.getAttribute('placeholder'), stack: new Error().stack});
      document.addEventListener('focusin', window.__labelFocusListener, true);
    });
    setPhase('label-popup-preview');await labelTrigger.click();
    const extension = page.locator('.new-label-container:visible');
    const searchInput = page.locator('.bk-select-search-input:visible, .collection-label-search input:visible');
    const options = page.locator('.bk-option:visible, .collection-label-picker .t-select-option:visible');
    await expect(extension).toHaveCount(1);await expect(searchInput).toHaveCount(1);
    const initialOptions = await options.allTextContents();
    await waitForUiIdle(searchInput);
    const popupLayout = await searchInput.evaluate(element => {
      const chain = [];
      for (let node = element; node && chain.length < 10; node = node.parentElement) {
        const rect = node.getBoundingClientRect(), style = getComputedStyle(node);
        chain.push({tag: node.tagName, class: node.className, rect: {x: rect.x, y: rect.y, width: rect.width, height: rect.height}, padding: style.padding, margin: style.margin, border: style.border, transform: style.transform, display: style.display});
      }
      document.removeEventListener('focusin', window.__labelFocusListener, true);
      const instance=element.__vueParentComponent;
      return {inputRefDebug: {name: instance?.type?.name, exposedKeys: Object.keys(instance?.exposed??{}), refTag: instance?.exposed?.inputRef?.value?.tagName, sameElement: instance?.exposed?.inputRef?.value === element, focusSource: instance?.exposed?.focus?.toString()}, chain, focusEvents: window.__labelFocusEvents, active: {tag: document.activeElement.tagName, class: document.activeElement.className}};
    });
    writeFileSync(resolve(privateDir, 'label-popup-layout.debug.json'), JSON.stringify(popupLayout, null, 2), {mode: 0o600});
    await checkpoint('label-popup-preview', [{semanticId: 'collection.label.search', selector: '.bk-select-search-input, .collection-label-search input'}]);
    setPhase('label-filter-no-match');
    await searchInput.fill('__bklog_no_such_label_20261111__');
    await expect.poll(() => options.count()).toBe(0);
    await waitForUiIdle(searchInput);
    await checkpoint('label-filter-no-match', [{semanticId: 'collection.label.search', selector: '.bk-select-search-input, .collection-label-search input'}]);
    await searchInput.fill('');await expect.poll(() => options.allTextContents()).toEqual(initialOptions);
    setPhase('label-required-validation');await extension.locator('.add-new-label').click();
    const draft = extension.locator('.new-label-input input');await expect(draft).toHaveCount(1);
    await draft.fill('');await extension.locator('.operate-button .icon-check-line').click();
    const formDiagnostic = await extension.evaluate(root => [...root.querySelectorAll('form, [class*="form"], [class*="error"]')].map(node => ({tag: node.tagName, class: node.className, requiredMessage: node.textContent.includes('必填项'), rect: {x: node.getBoundingClientRect().x, y: node.getBoundingClientRect().y, width: node.getBoundingClientRect().width, height: node.getBoundingClientRect().height}})));
    writeFileSync(resolve(privateDir, 'label-validation.debug.json'), JSON.stringify(formDiagnostic, null, 2), {mode: 0o600});
    const error = extension.locator('.bk-form-item.is-error, .t-input.t-is-error');
    await expect(error).toHaveCount(1);
    // V2 uses a tooltip, TDesign may render an inline message. Inspect the
    // actual required-error feedback instead of assuming the same wrapper.
    const tooltipIcon = error.locator('.tooltips-icon');
    if (await tooltipIcon.count()) await tooltipIcon.hover();
    await expect(page.getByText('必填项', {exact: true}).filter({visible: true})).toHaveCount(1);
    await checkpoint('label-required-validation');
    if (labelCancelPreview) {
    await page.evaluate(() => {
      const root = document.querySelector('.new-label-container');
      window.__labelCancelDiagnostic = [];
      window.__labelCancelObserver = new MutationObserver(records => window.__labelCancelDiagnostic.push(...records.map(record => ({type: record.type, attribute: record.attributeName, oldValue: record.oldValue, targetClass: record.target.className, added: [...record.addedNodes].map(node => node.className), removed: [...record.removedNodes].map(node => node.className)}))));
      window.__labelCancelObserver.observe(root, {attributes: true, attributeOldValue: true, childList: true, subtree: true});
    });
    await extension.locator('.operate-button .icon-close-line-2').click();
    const cancelDiagnostic = await page.evaluate(() => {window.__labelCancelObserver.disconnect();return window.__labelCancelDiagnostic;});
    writeFileSync(resolve(privateDir, 'label-cancel.debug.json'), JSON.stringify(cancelDiagnostic, null, 2), {mode: 0o600});

    await expect(extension.locator('.new-label-input'), 'DRAFT_CANCEL_DID_NOT_CLOSE').toHaveCount(0);
    }
    await searchInput.press('Escape');await expect(extension).toHaveCount(0);
    await labelTrigger.click();await expect(extension).toHaveCount(1);
    await expect(extension.locator('.new-label-input'), 'REOPEN_DRAFT_DID_NOT_RESET').toHaveCount(0);await expect(searchInput).toHaveValue('');
    await searchInput.press('Escape');await expect(extension).toHaveCount(0);
    await checkpoint(labelCancelPreview ? 'label-cancel-restored' : 'label-close-restored');
    const blocked = entries.filter(e => e.policy.decision === 'BLOCK' && e.policy.reason !== 'EXCLUDED_TELEMETRY');
    if (blocked.length) throw new Error('LABEL_PREVIEW_ATTEMPTED_WRITE:' + blocked.map(e => e.path).join(','));
  }

  if (navClusterPreview) {
    const nav = page.locator('[data-test-id="navBox_nav_es-cluster-manage"]');
    await expect(nav).toHaveCount(1);await expect(nav).toBeVisible();
    const navRect = await nav.boundingBox();
    if (!navRect || navRect.width > 80) throw new Error('NAVIGATION_SEED_NOT_COLLAPSED');
    const icon = nav.locator('.navigation-menu-item-icon, i');await expect(icon).toHaveCount(1);
    await checkpoint('collapsed-nav-ready', [{semanticId:'management.navigation.es-cluster',selector:'a.nav-item:has([data-test-id="navBox_nav_es-cluster-manage"]), a.nav-item[data-test-id="navBox_nav_es-cluster-manage"]'}]);
    setPhase('nav-open-cluster');await icon.click();
    await expect(page).toHaveURL(/#\/manage\/es-cluster-manage\?/);
    await page.mouse.move(1000, 80);
    const sidebar = page.locator('.bk-log-navigation .navigation-nav, .manage-sidebar-slider');
    await expect(sidebar).toHaveCount(1);
    await expect.poll(async () => Math.round((await sidebar.boundingBox())?.width ?? -1)).toBe(60);
    await waitForUiIdle(sidebar);
    const navQuery = new URLSearchParams(new URL(page.url()).hash.split('?')[1]);
    if (navQuery.get('spaceUid') !== 'bkcc__5000140') throw new Error('NAV_SPACE_CONTEXT_LOST');
    const path = '/api/v1/databus/storage/';
    await expect.poll(() => entries.some(entry => entry.path === path && entry.complete), {timeout:60000}).toBe(true);
    const listRecord = entries.find(entry => entry.path === path && entry.complete);
    const clusters = JSON.parse(readBody(listRecord)).data;
    if (!Array.isArray(clusters)) throw new Error('CLUSTER_LIST_PROTOCOL_MISMATCH');
    const requestData = readRequest(listRecord);
    const requestUrl = new URL(requestData.url);
    if (requestUrl.searchParams.get('bk_biz_id') !== '5000140' || requestUrl.searchParams.get('cluster_type') !== 'elasticsearch') throw new Error('NAV_CLUSTER_REQUEST_CONTEXT_LOST');
    const table = page.locator('[data-test-id="esAccessBox_table_esAccessTableBox"]');await expect(table).toHaveCount(1);
    if (clusters.length) {
      await expect.poll(() => entries.some(entry => entry.path === '/api/v1/databus/storage/batch_connectivity_detect/' && entry.complete), {timeout:60000}).toBe(true);
      const first = clusters[0].cluster_config;
      const body = table.locator('.bk-table-body-wrapper tbody, .t-table__body');
      const row = body.locator('tr').filter({has:page.getByText(String(first.cluster_id), {exact:true})});
      await expect(row).toHaveCount(1);await expect(row).toContainText(first.display_name || '--');
    } else {
      await expect(table.locator('tbody tr:not(.t-table__empty-row)')).toHaveCount(0);
      await expect(table.locator('.bk-table-empty-block, .t-table__empty')).toBeVisible();
      const image = table.locator('.empty-status-container .exception-image');
      await expect(image).toHaveCount(1);
      await expect.poll(() => image.evaluate(element => element.complete && element.naturalWidth > 0)).toBe(true);
    }
    await expect.poll(() => entries.filter(entry => entry.policy.decision === 'ALLOW' && !entry.complete && !entry.failure && !entry.captureError).length, {timeout:60000}).toBe(0);
    await expect(table.locator('.bk-loading:visible')).toHaveCount(0);
    await expect(page.locator('[data-testid="cluster-table-loading"] > .t-loading__overlay:visible')).toHaveCount(0);
    await waitForUiIdle(table);
    await checkpoint('nav-cluster-ready', clusters.length ? [] : [{semanticId:'cluster.empty.image',selector:'[data-test-id="esAccessBox_table_esAccessTableBox"] .exception-image'},{semanticId:'cluster.empty.text',selector:'[data-test-id="esAccessBox_table_esAccessTableBox"] .empty-text'}]);
    if (clusterSearchPreview) {
      await page.clock.setSystemTime(await page.evaluate(() => Date.now()) + 1);
      if (clusters.length) throw new Error('CLUSTER_SEARCH_EMPTY_REQUIRES_REAL_EMPTY_BASELINE');
      setPhase('cluster-search-local');
      const search = page.locator('[data-test-id="esAccessBox_input_search"] input');
      const empty = table.locator('.empty-text');
      const requestsBefore = entries.length;
      await search.fill('__migration_no_matching_cluster__');
      await expect(empty).toHaveText('暂无数据');
      const submit = page.locator('[data-test-id="esAccessBox_input_search"] .input-right-icon, [data-test-id="esAccessBox_input_search"] .cluster-search-submit');
      await expect(submit).toHaveCount(1);await submit.click();
      await expect(empty).toHaveText('搜索结果为空');
      await checkpoint('cluster-search-empty', [{semanticId:'cluster.empty.text',selector:'[data-test-id="esAccessBox_table_esAccessTableBox"] .empty-text'}]);
      await search.hover();
      await page.locator('[data-test-id="esAccessBox_input_search"] .clear-icon, [data-test-id="esAccessBox_input_search"] .t-input__suffix-clear').click();
      await expect(search).toHaveValue('');await expect(empty).toHaveText('暂无数据');
      await search.fill('__migration_no_matching_cluster__');await search.press('Enter');
      await expect(empty).toHaveText('搜索结果为空');
      // The separate clear-filter operation re-fetches; it is not a local input clear.
      await search.hover();
      await page.locator('[data-test-id="esAccessBox_input_search"] .clear-icon, [data-test-id="esAccessBox_input_search"] .t-input__suffix-clear').click();
      await expect(search).toHaveValue('');await expect(empty).toHaveText('暂无数据');
      if (entries.length !== requestsBefore) throw new Error('CLUSTER_LOCAL_SEARCH_ISSUED_REQUEST');
      await checkpoint('cluster-search-restored', [{semanticId:'cluster.empty.text',selector:'[data-test-id="esAccessBox_table_esAccessTableBox"] .empty-text'}]);
    }
    const blocked = entries.filter(entry => entry.policy.decision === 'BLOCK' && entry.policy.reason !== 'EXCLUDED_TELEMETRY');
    if (blocked.length) throw new Error('NAVIGATION_UNREVIEWED_DEPENDENCY:' + blocked.map(entry => entry.path).join(','));
  }

}
