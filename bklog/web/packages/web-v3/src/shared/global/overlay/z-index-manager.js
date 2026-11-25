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

'use strict';

/**
 * 全局 z-index 分层。页面布局只用 BASE–FLOAT_FIXED，浮层从 DROPDOWN 起递增。
 * Drawer / Dialog / Popup 打开时走 nextZIndex，并挂到 body。
 * Message / 全屏遮罩走 nextMessageZIndex，始终高于浮层计数。
 */
const Z_INDEX_LAYERS = Object.freeze({
  BASE: 1,
  RAISED: 2,
  LOCAL: 3,
  TOOLBAR: 5,
  STICKY: 6,
  FIELD_STICKY: 8,
  PAGE: 20,
  PAGE_TOP: 40,
  FLOAT: 80,
  NAV: 100,
  NAV_TOP: 110,
  FLOAT_FIXED: 200,
  DROPDOWN: 2000,
  DRAWER: 2500,
  DIALOG: 3000,
  MESSAGE: 5000,
});

const LAYER_CSS_VARS = Object.freeze({
  '--bklog-z-base': 'BASE',
  '--bklog-z-raised': 'RAISED',
  '--bklog-z-local': 'LOCAL',
  '--bklog-z-toolbar': 'TOOLBAR',
  '--bklog-z-sticky': 'STICKY',
  '--bklog-z-field-sticky': 'FIELD_STICKY',
  '--bklog-z-page': 'PAGE',
  '--bklog-z-page-top': 'PAGE_TOP',
  '--bklog-z-float': 'FLOAT',
  '--bklog-z-nav': 'NAV',
  '--bklog-z-nav-top': 'NAV_TOP',
  '--bklog-z-float-fixed': 'FLOAT_FIXED',
  '--bklog-z-dropdown': 'DROPDOWN',
  '--bklog-z-drawer': 'DRAWER',
  '--bklog-z-dialog': 'DIALOG',
  '--bklog-z-message': 'MESSAGE',
});

const isExplicitZIndex = (value) => {
  if (value === undefined || value === null || value === 'default') return false;
  return Number.isFinite(Number(value));
};

// Monitor drawers live below DIALOG. Keep the floor in the shared layer contract.
const MONITOR_OVERLAY_ZINDEX_BASE = Z_INDEX_LAYERS.DIALOG;
const getOverlayZIndexStart = (target = typeof globalThis !== 'undefined' ? globalThis : undefined) => {
  const win = target?.window || target;
  return win?.__IS_MONITOR_COMPONENT__ ? MONITOR_OVERLAY_ZINDEX_BASE : Z_INDEX_LAYERS.DROPDOWN;
};

const createZIndexManager = (start = Z_INDEX_LAYERS.DROPDOWN, target = typeof globalThis !== 'undefined' ? globalThis : undefined) => {
  let current = start;
  let messageCurrent = Z_INDEX_LAYERS.MESSAGE;
  const publish = () => {
    const win = target?.window || target;
    const root = win?.document?.documentElement;
    if (!root) return;
    root.style.setProperty('--bklog-z-overlay', String(current));
    root.style.setProperty('--bklog-z-message-current', String(messageCurrent));
  };
  return {
    layers: Z_INDEX_LAYERS,
    getCurrent() {
      return current;
    },
    // 无参或 'default' 时递增。传入数字时沿用该层，兼容 bk-magic 的 nextZIndex(explicit)。
    nextZIndex(explicit) {
      if (isExplicitZIndex(explicit)) {
        const numeric = Number(explicit);
        if (numeric < Z_INDEX_LAYERS.MESSAGE) current = Math.max(current, numeric);
        publish();
        return numeric;
      }
      current = Math.max(current, getOverlayZIndexStart(target));
      current += 1;
      publish();
      return current;
    },
    // 提示、全屏遮罩。起点在浮层计数之上，避免被 Dialog 盖住。
    nextMessageZIndex() {
      messageCurrent = Math.max(messageCurrent, current, Z_INDEX_LAYERS.MESSAGE) + 1;
      publish();
      return messageCurrent;
    },
    // bk-magic / ip-selector 弹窗通过 nextTickIndex(step, explicit) 取层号。
    nextTickIndex(step = 1, explicit = 'default') {
      if (isExplicitZIndex(explicit)) {
        const numeric = Number(explicit);
        if (numeric < Z_INDEX_LAYERS.MESSAGE) current = Math.max(current, numeric);
        publish();
        return numeric;
      }
      current = Math.max(current, getOverlayZIndexStart(target));
      const delta = Number(step);
      current += Number.isFinite(delta) && delta > 0 ? delta : 1;
      publish();
      return current;
    },
    reset(next = start) {
      current = next;
      messageCurrent = Z_INDEX_LAYERS.MESSAGE;
      publish();
      return current;
    },
  };
};

const publishLayerVariables = (win, layers = Z_INDEX_LAYERS) => {
  const root = win.document?.documentElement;
  if (!root) return;
  Object.entries(LAYER_CSS_VARS).forEach(([cssVar, layerName]) => {
    root.style.setProperty(cssVar, String(layers[layerName]));
  });
};

const installOverlayWatcher = (win, manager) => {
  if (!win.document?.body || win.__bk_zIndex_watcher) return;
  const seen = new WeakSet();
  const ownsOverlay = el => {
    const traceBuild = typeof __BKLOG_TRACE_EMBEDDED__ !== 'undefined' && __BKLOG_TRACE_EMBEDDED__;
    return !(traceBuild || win.__IS_MONITOR_TRACE__) || el.closest('.monitor-trace-log, .bklog-text-tooltip') !== null;
  };
  const assignPopup = (el) => {
    if (!ownsOverlay(el) || seen.has(el) || el.style.zIndex) return;
    seen.add(el);
    const zIndex = manager.nextZIndex();
    win.document.documentElement.style.setProperty('--bklog-z-popup', String(zIndex));
  };
  const assignMessage = (el) => {
    if (!ownsOverlay(el) || seen.has(el)) return;
    seen.add(el);
    const zIndex = manager.nextMessageZIndex();
    el.style.zIndex = String(zIndex);
  };
  const scan = (node) => {
    if (!(node instanceof win.Element)) return;
    if (node.matches('.t-popup')) assignPopup(node);
    node.querySelectorAll?.('.t-popup').forEach(assignPopup);
    if (node.matches('.t-message__list, .t-notification')) assignMessage(node);
    node.querySelectorAll?.('.t-message__list, .t-notification').forEach(assignMessage);
  };
  const observer = new win.MutationObserver((records) => {
    records.forEach((record) => {
      record.addedNodes.forEach(scan);
    });
  });
  observer.observe(win.document.body, { childList: true, subtree: true });
  win.document.querySelectorAll('.t-popup, .t-message__list, .t-notification').forEach(scan);
  win.__bk_zIndex_watcher = observer;
};

const ensureMagicZIndexApi = (manager, target) => {
  if (!manager) return manager;
  if (typeof manager.nextMessageZIndex === 'function' && typeof manager.nextTickIndex === 'function' && typeof manager.getCurrent === 'function') {
    return manager;
  }
  const seeded = createZIndexManager(Math.max(manager.getCurrent?.() ?? 0, manager.zIndex ?? 0, getOverlayZIndexStart(target)), target);
  manager.nextZIndex = seeded.nextZIndex.bind(seeded);
  manager.nextTickIndex = seeded.nextTickIndex.bind(seeded);
  manager.nextMessageZIndex = seeded.nextMessageZIndex.bind(seeded);
  manager.getCurrent = seeded.getCurrent.bind(seeded);
  manager.reset = seeded.reset.bind(seeded);
  manager.layers = Z_INDEX_LAYERS;
  return manager;
};

const installZIndexManager = (target = typeof globalThis !== 'undefined' ? globalThis : undefined) => {
  if (!target) return null;
  const win = target.window || target;
  const manager = win.__bk_zIndex_manager?.nextZIndex
    ? ensureMagicZIndexApi(win.__bk_zIndex_manager, win)
    : createZIndexManager(getOverlayZIndexStart(win), win);
  win.__bk_zIndex_manager = manager;
  publishLayerVariables(win, manager.layers || Z_INDEX_LAYERS);
  win.document?.documentElement?.style.setProperty('--bklog-z-popup', String(Math.max(manager.getCurrent(), getOverlayZIndexStart(win))));
  installOverlayWatcher(win, manager);
  return manager;
};

/** Called after Monitor flags are set, including when modules were imported earlier. */
const ensureMonitorOverlayZIndex = (target = typeof globalThis !== 'undefined' ? globalThis : undefined) => {
  const win = target?.window || target;
  if (!win?.__IS_MONITOR_COMPONENT__) return null;
  const manager = installZIndexManager(win);
  manager.nextZIndex(Math.max(manager.getCurrent(), MONITOR_OVERLAY_ZINDEX_BASE));
  return manager;
};

const manager = installZIndexManager();

export { MONITOR_OVERLAY_ZINDEX_BASE, getOverlayZIndexStart, ensureMonitorOverlayZIndex, Z_INDEX_LAYERS, createZIndexManager, installZIndexManager, manager as zIndexManager };
export default manager;
