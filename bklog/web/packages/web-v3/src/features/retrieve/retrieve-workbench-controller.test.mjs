/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台 (BlueKing PaaS):
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

import { RetrieveWorkbenchController } from './retrieve-workbench-controller.ts';

const route = {
  indexSetId: '38077',
  spaceUid: 'bkcc__5000140',
  bizId: '5000140',
  tab: 'origin',
};

describe('RetrieveWorkbenchController', () => {
  it('AC-001 initializes a V2 workbench snapshot from route', () => {
    const state = new RetrieveWorkbenchController(route, 1_710_000_000_000).getState();
    assert.equal(state.routeState.indexSetId, '38077');
    assert.equal(state.dataState.activeTab, 'origin');
    assert.equal(state.queryState.mode, 'ui');
    assert.equal(state.uiState.favoriteShown, false);
    assert.equal(state.queryState.timeRange.endTime, 1_710_000_000_000);
  });

  it('AC-002 turns user actions into a shared search context', () => {
    const controller = new RetrieveWorkbenchController(route, 1_710_000_000_000);
    controller.dispatch({ type: 'query/change', keyword: 'error', mode: 'sql' });
    controller.dispatch({ type: 'favorite/apply', favoriteId: 'fav-1', keyword: 'status:500' });
    const state = controller.dispatch({ type: 'time/change', timeRange: { startTime: 1, endTime: 2 } });
    assert.equal(state.queryState.keyword, 'status:500');
    assert.equal(state.queryState.mode, 'sql');
    assert.equal(state.queryState.page, 1);
    assert.equal(state.dataState.favoriteId, 'fav-1');
    assert.deepEqual(state.queryState.timeRange, { startTime: 1, endTime: 2 });
  });

  it('AC-003 isolates dialog and data errors', () => {
    const controller = new RetrieveWorkbenchController(route);
    controller.dispatch({ type: 'dialog/open', dialog: 'download' });
    controller.dispatch({ type: 'error/set', scope: 'fields', message: 'field failed' });
    controller.dispatch({ type: 'error/set', scope: 'dialog', message: 'download failed' });
    const state = controller.dispatch({ type: 'dialog/close' });
    assert.equal(state.uiState.activeDialog, null);
    assert.equal(state.errorState.fields, 'field failed');
    assert.equal(state.errorState.dialog, 'download failed');
  });
});
