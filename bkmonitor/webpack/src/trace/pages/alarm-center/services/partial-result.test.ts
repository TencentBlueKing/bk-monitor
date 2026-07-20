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
import test from 'node:test';

import { getPartialResultState } from './partial-result.ts';

test('normalizes an incomplete backend response for the alarm table', () => {
  const state = getPartialResultState({
    is_partial: true,
    partial_reasons: [
      {
        code: 'notice_way_candidate_limit',
        scopes: ['alerts', 'total'],
        scanned_candidate_count: 10000,
        candidate_limit: 10000,
      },
    ],
    total_relation: 'gte',
  });

  assert.deepEqual(state, {
    isPartial: true,
    partialReasons: [
      {
        code: 'notice_way_candidate_limit',
        scopes: ['alerts', 'total'],
        scanned_candidate_count: 10000,
        candidate_limit: 10000,
      },
    ],
    totalRelation: 'gte',
  });
});

test('uses complete defaults for older backend responses', () => {
  assert.deepEqual(getPartialResultState({}), {
    isPartial: false,
    partialReasons: [],
    totalRelation: 'eq',
  });
});

test('keeps a lower-bound total separate from partial result state', () => {
  assert.deepEqual(
    getPartialResultState({
      is_partial: false,
      partial_reasons: [],
      total_relation: 'gte',
    }),
    {
      isPartial: false,
      partialReasons: [],
      totalRelation: 'gte',
    }
  );
});
