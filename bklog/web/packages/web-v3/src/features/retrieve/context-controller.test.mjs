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

import { ContextController } from './context-controller.ts';

const records = [
  { id: '1', dtEventTimeStamp: 1, log: 'one' },
  { id: '2', dtEventTimeStamp: 2, log: 'two' },
  { id: '3', dtEventTimeStamp: 3, log: 'three' },
];

describe('ContextController', () => {
  it('AC-001 waits while the main search is loading', () => {
    const state = new ContextController().open(records, '2', true);
    assert.equal(state.uiState, 'waiting');
    assert.equal(state.before.length, 0);
  });

  it('AC-002 returns neighbors around the anchor row', () => {
    const state = new ContextController().open(records, '2', false, 1);
    assert.equal(state.uiState, 'success');
    assert.deepEqual(state.before.map(item => item.id), ['1']);
    assert.deepEqual(state.after.map(item => item.id), ['3']);
  });
});
