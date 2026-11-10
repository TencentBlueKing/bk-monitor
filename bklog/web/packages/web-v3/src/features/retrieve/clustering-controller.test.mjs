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

import { ClusteringController } from './clustering-controller.ts';

describe('ClusteringController', () => {
  it('AC-001 groups similar logs and sorts by count', () => {
    const groups = new ClusteringController().group([
      { id: '1', dtEventTimeStamp: 1, log: 'error timeout from api 12' },
      { id: '2', dtEventTimeStamp: 2, log: 'error timeout from api 34' },
      { id: '3', dtEventTimeStamp: 3, log: 'info user login' },
    ]);
    assert.equal(groups[0].count, 2);
    assert.ok(groups[0].pattern.includes('error'));
  });

  it('AC-002 filters groups by query', () => {
    const groups = new ClusteringController().group([
      { id: '1', dtEventTimeStamp: 1, log: 'error timeout from api' },
      { id: '2', dtEventTimeStamp: 2, log: 'info user login' },
    ], 'login');
    assert.equal(groups.length, 1);
    assert.ok(groups[0].sample.includes('login'));
  });
});
