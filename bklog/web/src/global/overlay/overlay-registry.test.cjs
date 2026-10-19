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

const assert = require('node:assert/strict');
const test = require('node:test');

const {
  OverlayRegistry,
  createDialogVisibleState,
  isClickInsideClosest,
  isValidAnchorRect,
  resolvePopperPlacementRect,
  shouldHideOnOutsideClick,
} = require('./overlay-registry.js');

const createRegistry = () => new OverlayRegistry();

test('same group overlays are mutually exclusive', () => {
  const registry = createRegistry();
  const hidden = [];

  registry.register('menu-a', { group: 'favorite-menu', hide: () => hidden.push('menu-a') });
  registry.register('menu-b', { group: 'favorite-menu', hide: () => hidden.push('menu-b') });
  registry.open('menu-a');
  registry.open('menu-b');

  assert.equal(registry.isOpen('menu-a'), false);
  assert.equal(registry.isOpen('menu-b'), true);
  assert.deepEqual(hidden, ['menu-a']);
});

test('hiding parent hides children first', () => {
  const registry = createRegistry();
  const hidden = [];

  registry.register('outer', { hide: () => hidden.push('outer') });
  registry.register('inner', { parentId: 'outer', hide: () => hidden.push('inner') });
  registry.open('outer');
  registry.open('inner');
  registry.hide('outer');

  assert.deepEqual(hidden, ['inner', 'outer']);
  assert.equal(registry.isOpen('inner'), false);
  assert.equal(registry.isOpen('outer'), false);
});

test('opening a child does not hide its parent even in the same group', () => {
  const registry = createRegistry();

  registry.register('outer', { group: 'grade', hide: () => undefined });
  registry.register('inner', { group: 'grade', parentId: 'outer', hide: () => undefined });
  registry.open('outer');
  registry.open('inner');

  assert.equal(registry.isOpen('outer'), true);
  assert.equal(registry.isOpen('inner'), true);
});

test('anchor lost is treated as hide', () => {
  const registry = createRegistry();
  let hidden = false;

  registry.register('suggest', { hide: () => { hidden = true; } });
  registry.open('suggest');
  registry.notifyAnchorLost('suggest');

  assert.equal(hidden, true);
  assert.equal(registry.isOpen('suggest'), false);
});

test('dispose removes the record after hide', () => {
  const registry = createRegistry();

  registry.register('temp', { parentId: 'missing' });
  registry.open('temp');
  registry.dispose('temp');

  assert.equal(registry.get('temp'), null);
  assert.deepEqual(registry.getStack(), []);
});

test('click-outside uses closest instead of classList.contains', () => {
  const inner = {
    closest(selector) {
      return selector === '.bklog-popover-stop' ? inner : null;
    },
    classList: {
      contains() {
        throw new Error('classList.contains must not be used');
      },
    },
  };

  assert.equal(isClickInsideClosest({ target: inner }, ['.bklog-popover-stop']), true);
  assert.equal(shouldHideOnOutsideClick({ target: inner }, { ignoreSelector: '.bklog-popover-stop' }), false);
  assert.equal(shouldHideOnOutsideClick({ target: inner }, { rootSelector: '.other-root' }), true);
});

test('invalid anchor rect must not be forwarded to popper', () => {
  assert.equal(isValidAnchorRect({ width: 0, height: 0, x: 0, y: 0 }), false);
  assert.equal(resolvePopperPlacementRect({ width: 0, height: 10, x: 0, y: 0 }), null);
  assert.deepEqual(resolvePopperPlacementRect({ width: 12, height: 20, x: 8, y: 16 }), {
    width: 12,
    height: 20,
    x: 8,
    y: 16,
  });
});

test('z-index comes from bk manager or registry fallback, never a hardcoded 99999', () => {
  const registry = createRegistry();
  const previousWindow = globalThis.window;
  globalThis.window = { __bk_zIndex_manager: { nextZIndex: () => 3210 } };

  try {
    registry.register('layer');
    const record = registry.open('layer');
    assert.equal(record.zIndex, 3210);
    assert.equal([99999, 100000].includes(record.zIndex), false);
  } finally {
    globalThis.window = previousWindow;
  }

  const fallback = createRegistry();
  fallback.register('fallback');
  const fallbackRecord = fallback.open('fallback');
  assert.ok(fallbackRecord.zIndex > 2000);
  assert.equal([99999, 100000].includes(fallbackRecord.zIndex), false);
});

test('findParentIdByElement resolves the visible ancestor overlay', () => {
  const registry = createRegistry();
  const child = {
    closest(selector) {
      return selector === '[data-overlay-id="outer"]' ? child : null;
    },
  };

  registry.register('outer', { rootSelector: '[data-overlay-id="outer"]' });
  registry.open('outer');

  assert.equal(registry.findParentIdByElement(child), 'outer');
  assert.equal(registry.isClickInsideRecord({ target: child }, 'outer'), true);
});

test('dialog visible writes back false so the next open is a real change', () => {
  const events = [];
  const state = createDialogVisibleState(true, {
    onOpen: () => events.push('open'),
    onHide: () => events.push('hide'),
  });

  assert.equal(state.getVisible(), true);
  assert.equal(state.setVisible(true), true);
  assert.deepEqual(events, []);

  assert.equal(state.onValueChange(false), false);
  assert.deepEqual(events, ['hide']);
  assert.equal(state.setVisible(true), true);
  assert.deepEqual(events, ['hide', 'open']);
});
