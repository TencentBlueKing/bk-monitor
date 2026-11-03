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
const { test } = require('node:test');
const { FAVORITE_MENU_HIDE_DELAY, createFavoriteMenuHoverState } = require('./collect-list-menu-hover.js');

test('shown keeps the favorite item hover open id', () => {
  const hover = createFavoriteMenuHoverState();
  hover.shown(12);
  assert.equal(hover.getOpenId(), 12);
  assert.equal(hover.isMenuOpen(12), true);
  assert.equal(hover.isMenuOpen(13), false);
});

test('hidden clears the same id only after the hide delay', t => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  const hover = createFavoriteMenuHoverState();
  hover.shown(12);
  hover.hidden(12);
  assert.equal(hover.getOpenId(), 12);
  t.mock.timers.tick(FAVORITE_MENU_HIDE_DELAY - 1);
  assert.equal(hover.getOpenId(), 12);
  t.mock.timers.tick(1);
  assert.equal(hover.getOpenId(), null);
});

test('shown before hide delay keeps hover and cancels the pending hide', t => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  const hover = createFavoriteMenuHoverState();
  hover.shown(12);
  hover.hidden(12);
  hover.shown(12);
  t.mock.timers.tick(FAVORITE_MENU_HIDE_DELAY);
  assert.equal(hover.getOpenId(), 12);
});

test('stale hide for a previous item does not clear the newly opened item', t => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  const hover = createFavoriteMenuHoverState();
  hover.shown(12);
  hover.hidden(12);
  hover.shown(13);
  t.mock.timers.tick(FAVORITE_MENU_HIDE_DELAY);
  assert.equal(hover.getOpenId(), 13);
  assert.equal(hover.isMenuOpen(13), true);
});

test('dispose cancels a pending hide timer', t => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  const hover = createFavoriteMenuHoverState();
  hover.shown(12);
  hover.hidden(12);
  hover.dispose();
  t.mock.timers.tick(FAVORITE_MENU_HIDE_DELAY);
  assert.equal(hover.getOpenId(), 12);
});
