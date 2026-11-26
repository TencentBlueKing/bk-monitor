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

const resolveLayerFloor = (layer) => {
  if (typeof layer === 'string' && Object.prototype.hasOwnProperty.call(Z_INDEX_LAYERS, layer)) {
    return Z_INDEX_LAYERS[layer];
  }
  return undefined;
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
    // 按分层底线单调递增分配（DROPDOWN / DRAWER / DIALOG / MESSAGE）。
    nextLayerZIndex(layer = 'DROPDOWN') {
      if (layer === 'MESSAGE') return this.nextMessageZIndex();
      const floor = resolveLayerFloor(layer) ?? Z_INDEX_LAYERS.DROPDOWN;
      current = Math.max(current, getOverlayZIndexStart(target), floor);
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

const OVERLAY_QUERY_SELECTOR = '.t-popup, .t-drawer, .t-dialog__ctx, .t-message__list, .t-notification, [data-tippy-root]';
const TIPPY_DEFAULT_ZINDEX = '9999';

const getOverlayKind = (el) => {
  const cl = el.classList;
  if (cl && typeof cl.contains === 'function') {
    if (cl.contains('t-dialog__ctx')) return 'DIALOG';
    if (cl.contains('t-drawer')) return 'DRAWER';
    if (cl.contains('t-popup')) return 'DROPDOWN';
    if (cl.contains('t-message__list') || cl.contains('t-notification')) return 'MESSAGE';
  } else if (typeof el.matches === 'function') {
    if (el.matches('.t-dialog__ctx')) return 'DIALOG';
    if (el.matches('.t-drawer')) return 'DRAWER';
    if (el.matches('.t-popup')) return 'DROPDOWN';
    if (el.matches('.t-message__list, .t-notification')) return 'MESSAGE';
  }
  if ((typeof el.hasAttribute === 'function' && el.hasAttribute('data-tippy-root')) || el.matches?.('[data-tippy-root]')) {
    return 'TIPPY';
  }
  return null;
};

const isOverlayVisible = (el, kind) => {
  if (el.style?.display === 'none') return false;
  if (kind === 'DRAWER') {
    if (el.classList && typeof el.classList.contains === 'function') {
      return el.classList.contains('t-drawer--open');
    }
    return true;
  }
  if (kind === 'DROPDOWN' || kind === 'TIPPY') {
    if (el.style?.visibility === 'hidden') return false;
  }
  return true;
};

const allocateLayer = (manager, layer) => {
  if (layer === 'MESSAGE') return manager.nextMessageZIndex();
  if (typeof manager.nextLayerZIndex === 'function') return manager.nextLayerZIndex(layer);
  const floor = resolveLayerFloor(layer);
  if (floor !== undefined) manager.nextZIndex(floor);
  return manager.nextZIndex();
};

const writeElementZIndex = (el, zIndex) => {
  // 写入元素级 CSS 变量 --bklog-el-z，避免 Vue 重新 patch style:{ zIndex: undefined } 时清除内联 z-index。
  if (typeof el.style?.setProperty === 'function') {
    el.style.setProperty('--bklog-el-z', String(zIndex));
  } else if (el.style) {
    el.style.zIndex = String(zIndex);
  }
};

const installOverlayWatcher = (win, manager) => {
  if (!win.document?.body || win.__bk_zIndex_watcher) return;
  const openState = new WeakMap();
  const ownsOverlay = el => {
    const traceBuild = typeof __BKLOG_TRACE_EMBEDDED__ !== 'undefined' && __BKLOG_TRACE_EMBEDDED__;
    return !(traceBuild || win.__IS_MONITOR_TRACE__) || el.closest?.('.monitor-trace-log, .bklog-text-tooltip') !== null;
  };
  const syncExplicitZIndex = (el) => {
    const raw = el.style?.zIndex;
    if (raw === undefined || raw === null || raw === '') return false;
    const numeric = Number(raw);
    if (Number.isFinite(numeric) && numeric > 0 && numeric < Z_INDEX_LAYERS.MESSAGE) {
      manager.nextZIndex(numeric);
    }
    return true;
  };
  const bumpMessageContainer = (el) => {
    if (!ownsOverlay(el)) return;
    const zIndex = manager.nextMessageZIndex();
    if (el.style) {
      el.style.zIndex = String(zIndex);
      if (typeof el.style.setProperty === 'function') {
        el.style.setProperty('--bklog-el-z', String(zIndex));
      }
    }
  };
  const syncOverlay = (el) => {
    const kind = getOverlayKind(el);
    if (!kind || !ownsOverlay(el)) return;
    const visible = isOverlayVisible(el, kind);
    const wasVisible = openState.get(el) === true;
    if (!visible) {
      openState.set(el, false);
      return;
    }
    if (wasVisible) return;
    openState.set(el, true);

    if (kind === 'MESSAGE') {
      bumpMessageContainer(el);
      return;
    }
    if (kind === 'TIPPY') {
      const raw = el.style?.zIndex;
      const isDefaultTippy = !raw || (String(raw) === TIPPY_DEFAULT_ZINDEX && manager.getCurrent() < Number(TIPPY_DEFAULT_ZINDEX));
      if (isDefaultTippy) {
        const zIndex = allocateLayer(manager, 'DROPDOWN');
        if (el.style) el.style.zIndex = String(zIndex);
      } else {
        syncExplicitZIndex(el);
      }
      return;
    }
    // DIALOG / DRAWER / DROPDOWN：组件显式传了 :z-index 时同步全局计数器；未传时由元素级变量单调递增分配。
    if (syncExplicitZIndex(el)) return;
    const zIndex = allocateLayer(manager, kind);
    writeElementZIndex(el, zIndex);
  };
  const scan = (node) => {
    if (!(node instanceof win.Element)) return;
    syncOverlay(node);
    node.querySelectorAll?.(OVERLAY_QUERY_SELECTOR).forEach(syncOverlay);
  };
  const observer = new win.MutationObserver((records) => {
    records.forEach((record) => {
      if (record.type === 'attributes') {
        const target = record.target;
        if (target instanceof win.Element) syncOverlay(target);
        return;
      }
      if (record.addedNodes?.length) {
        record.addedNodes.forEach(scan);
        const target = record.target;
        if (target instanceof win.Element) {
          const messageHost = getOverlayKind(target) === 'MESSAGE'
            ? target
            : target.closest?.('.t-message__list, .t-notification');
          if (messageHost) bumpMessageContainer(messageHost);
        }
      }
    });
  });
  observer.observe(win.document.body, {
    childList: true,
    subtree: true,
    attributes: true,
    attributeFilter: ['style', 'class'],
  });
  win.document.querySelectorAll?.(OVERLAY_QUERY_SELECTOR).forEach(scan);
  win.__bk_zIndex_watcher = observer;
};

const ensureMagicZIndexApi = (manager, target) => {
  if (!manager) return manager;
  if (
    typeof manager.nextMessageZIndex === 'function' &&
    typeof manager.nextLayerZIndex === 'function' &&
    typeof manager.nextTickIndex === 'function' &&
    typeof manager.getCurrent === 'function'
  ) {
    return manager;
  }
  const seeded = createZIndexManager(Math.max(manager.getCurrent?.() ?? 0, manager.zIndex ?? 0, getOverlayZIndexStart(target)), target);
  manager.nextZIndex = seeded.nextZIndex.bind(seeded);
  manager.nextLayerZIndex = seeded.nextLayerZIndex.bind(seeded);
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
