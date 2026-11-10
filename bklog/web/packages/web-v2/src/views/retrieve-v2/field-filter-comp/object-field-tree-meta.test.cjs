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
  resolveObjectFieldChildrenCount,
  shouldShowObjectFieldTreeMeta,
} = require('./object-field-tree-meta.js');

test('display fields hide object tree chrome even with children_count', () => {
  assert.equal(shouldShowObjectFieldTreeMeta(false, 8), false);
});

test('optional field tree shows object child count', () => {
  assert.equal(shouldShowObjectFieldTreeMeta(true, 8), true);
});

test('optional field tree hides chrome when object has no children', () => {
  assert.equal(shouldShowObjectFieldTreeMeta(true, 0), false);
});

test('resolves children length before children_count', () => {
  assert.equal(resolveObjectFieldChildrenCount({ children: [{}, {}], children_count: 9 }), 2);
  assert.equal(resolveObjectFieldChildrenCount({ children_count: 4 }), 4);
  assert.equal(resolveObjectFieldChildrenCount({}), 0);
});
