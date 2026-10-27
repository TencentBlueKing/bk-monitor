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

import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import { ToolbarController } from './toolbar-controller.ts';

describe('ToolbarController', () => {
  it('AC-001 toggles favorite panel visibility', () => {
    const controller = new ToolbarController();
    assert.equal(controller.getState().favoriteShown, false);
    assert.equal(controller.toggleFavoriteShown().favoriteShown, true);
    assert.equal(controller.toggleFavoriteShown().favoriteShown, false);
  });

  it('AC-002 time preset change asks search to reset page', () => {
    const now = 1_710_000_000_000;
    const controller = new ToolbarController(null, now);
    const { intent, state } = controller.setTimePreset('1h', now);
    assert.equal(intent.resetPage, true);
    assert.equal(state.timePreset, '1h');
    assert.equal(intent.timeRange.endTime, now);
    assert.equal(intent.timeRange.startTime, now - 60 * 60 * 1000);
  });

  it('AC-003 auto refresh keeps current page', () => {
    const intents = [];
    const controller = new ToolbarController(intent => intents.push(intent));
    controller.setAutoRefresh(true, 10);
    const intent = controller.createRefreshIntent();
    assert.equal(intent.resetPage, false);
    assert.equal(controller.getState().uiState, 'refreshing');
    controller.dispose();
  });
});
