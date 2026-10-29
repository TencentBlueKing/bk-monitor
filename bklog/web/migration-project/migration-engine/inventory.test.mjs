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

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { analyzeSource } from './inventory.mjs';

test('AST route ownership survives nested objects, comments and adjacent routes', () => {
  const result = analyzeSource(`const List = () => import('@/views/list');
    export default [{ path: '/manage', name: 'manage', children: [
      { path: 'add', name: 'add', component: List, meta: { name: 'wrong' } },
      { path: 'edit/:id', name: 'edit', component: List }
    ] }, { path: '*', redirect: '/manage' }];`, 'routes.js');
  assert.deepEqual(result.routes.map(r => r.name), ['manage', 'add', 'edit', null]);
  assert.equal(result.routes[1].component, '@/views/list');
  assert.equal(result.routes[0].container, true);
  assert.equal(result.routes[3].redirect, true);
});

test('Vue SFC script imports are resolved without scanning template text as JS', () => {
  const result = analyzeSource(`<template><div>{{ text }}</div></template><script setup lang="ts">import X from './x'; const text: string = 'ok';</script>`, 'example.vue');
  assert.deepEqual(result.refs, ['./x']);
});
