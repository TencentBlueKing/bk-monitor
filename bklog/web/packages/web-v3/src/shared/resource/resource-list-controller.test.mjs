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

import { ResourceListController } from './resource-list-controller.ts';

const seed = [
  { id: '1', name: 'nginx-access', status: 'running', keyword: 'access' },
  { id: '2', name: 'nginx-error', status: 'failed', keyword: 'error' },
  { id: '3', name: 'app-info', status: 'ready', keyword: 'info' },
];

describe('ResourceListController', () => {
  it('AC-001 trims filter and matches name or keyword', () => {
    const controller = new ResourceListController(seed);
    controller.setFilterQuery('  error  ');
    assert.deepEqual(controller.getVisibleItems().map(item => item.id), ['2']);
  });

  it('AC-002 status filter keeps matching rows only', () => {
    const controller = new ResourceListController(seed);
    controller.setStatus('running');
    assert.deepEqual(controller.getVisibleItems().map(item => item.id), ['1']);
  });

  it('AC-003 rejects duplicate names', () => {
    const controller = new ResourceListController(seed);
    const state = controller.save({ name: 'nginx-access' });
    assert.equal(state.uiState, 'error');
    assert.equal(state.items.length, 3);
  });

  it('AC-004 remove drops the target row', () => {
    const controller = new ResourceListController(seed);
    controller.remove('2');
    assert.deepEqual(controller.getVisibleItems().map(item => item.id), ['1', '3']);
  });
});
