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

import { RealtimeController } from './realtime-controller.ts';

describe('RealtimeController', () => {
  it('AC-001 ignores append before start', () => {
    const controller = new RealtimeController(2);
    controller.append({ id: '1', dtEventTimeStamp: 1, log: 'a' });
    assert.equal(controller.getState().records.length, 0);
  });

  it('AC-002 caps the streaming buffer', () => {
    const controller = new RealtimeController(2);
    controller.start();
    controller.append({ id: '1', dtEventTimeStamp: 1, log: 'a' });
    controller.append({ id: '2', dtEventTimeStamp: 2, log: 'b' });
    controller.append({ id: '3', dtEventTimeStamp: 3, log: 'c' });
    assert.deepEqual(controller.getState().records.map(item => item.id), ['2', '3']);
    controller.stop();
    controller.append({ id: '4', dtEventTimeStamp: 4, log: 'd' });
    assert.deepEqual(controller.getState().records.map(item => item.id), ['2', '3']);
  });
});
