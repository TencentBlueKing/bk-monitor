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
const {
  resolveSyncErrorMessage,
  resolveSyncFailDetail,
} = require('../src/views/manage-v2/log-collection/components/create-operation/resolve-sync-fail-detail');

const options = {
  emptyResult: 'empty-result',
  missingReason: 'missing-reason',
};

assert.equal(
  resolveSyncFailDetail(
    [
      { id: 1, name: 'a', status: 'SUCCESS', message: '' },
      { id: 2, name: 'b', status: 'SUCCESS', message: '' },
    ],
    options,
  ),
  null,
  '全部成功不应返回失败详情',
);

assert.deepEqual(
  resolveSyncFailDetail(
    [
      { id: 1, name: 'ok-collector', status: 'SUCCESS', message: '' },
      { id: 2, name: 'bad-collector', status: 'FAILED', message: 'etl timeout' },
      { id: 3, status: 'FAILED' },
    ],
    options,
  ).items,
  [
    { name: 'bad-collector', message: 'etl timeout' },
    { name: '3', message: 'missing-reason' },
  ],
);

assert.deepEqual(resolveSyncFailDetail([], options), { items: [], summary: 'empty-result' });
assert.deepEqual(resolveSyncFailDetail({ message: 'oops' }, { ...options, errorMessage: 'api-error' }), {
  items: [],
  summary: 'api-error',
});

assert.equal(resolveSyncErrorMessage({ message: 'boom' }, 'fallback'), 'boom');
assert.equal(resolveSyncErrorMessage('  raw  ', 'fallback'), '  raw  ');
assert.equal(resolveSyncErrorMessage({}, 'fallback'), 'fallback');

console.log('resolve-sync-fail-detail-test: pass');
