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

import test from 'node:test';
import assert from 'node:assert/strict';
import { createPinia } from 'pinia';
import { native, effects, useCollect } from './helpers/application-store-fixture.mjs';
test('native application owns flat state and preserves named writes, persistence and isolation', async () => {
  const previous = globalThis.localStorage;
  globalThis.localStorage = { setItem: (...args) => effects.push(['localStorage', ...args]) };
  try {
    effects.length = 0;
    const a = native.useApplicationStore(createPinia()),
      b = native.useApplicationStore(createPinia());
    const names = [];
    a.$onAction(({ name }) => names.push(name));
    a.updateStorage({ width: 240 });
    a.updateAiMode({ active: true });
    a.updateApiError({ apiName: 'query', errorMessage: 'offline' });
    a.deleteApiError('query');
    assert.equal(a.storage.width, 240);
    assert.deepEqual(b.storage, {});
    assert.deepEqual(a.apiErrorInfo, {});
    assert.equal(a.$state.state, undefined);
    assert.deepEqual(names, ['updateStorage', 'updateAiMode', 'updateApiError', 'deleteApiError']);
    assert.ok(effects.some(([name, key]) => name === 'localStorage' && key === 'GLOBAL'));
    assert.ok(effects.some(([name, key]) => name === 'mirror' && key === 'GLOBAL'));
    a.resetState();
    assert.deepEqual(a.storage, {});
  } finally {
    globalThis.localStorage = previous;
  }
});
test('raw visible fields and derived visible fields remain separate; cross-domain getters use owning instance', () => {
  const pa = createPinia(),
    pb = createPinia(),
    a = native.useApplicationStore(pa),
    b = native.useApplicationStore(pb);
  a.visibleFields = [{ field_name: 'log' }, { field_name: 'hidden', hidden: true }];
  assert.equal(a.visibleFields.length, 2);
  assert.equal(a.resolvedVisibleFields.length, 1);
  a.collect.curCollect = { id: 7 };
  assert.equal(useCollect(pa).curCollect.id, 7);
  assert.deepEqual(b.collect.curCollect, {});
  assert.notEqual(a.requestPool, b.requestPool);
});
test('native user action keeps HTTP config, return value, root update and cache side effects', async () => {
  effects.length = 0;
  const store = native.useApplicationStore(createPinia());
  const value = await store.userInfo({ fixture: true }, { catchIsShowMessage: false });
  assert.deepEqual(value, { username: 'fixture' });
  assert.equal(store.user.username, 'fixture');
  assert.deepEqual(effects[0], ['userRequest', { query: { fixture: true }, config: { catchIsShowMessage: false } }]);
  assert.ok(effects.some(([name, key]) => name === 'cache' && key === 'userInfo/getUserInfo'));
});

test('disposing a native root store recreates its action owner while retaining Pinia state',()=>{
 const pinia=createPinia(),first=native.useApplicationStore(pinia);first.updateState({spaceUid:'retained'});first.$dispose();
 const second=native.useApplicationStore(pinia);assert.notEqual(second,first);assert.equal(second.spaceUid,'retained');second.updateState({spaceUid:'after-dispose'});assert.equal(pinia.state.value['bklog.application'].spaceUid,'after-dispose');
});
