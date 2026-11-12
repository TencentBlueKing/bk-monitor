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
import ts from 'typescript';
import { loadTypeScript } from './helpers/load-typescript.mjs';

const Popup = { name: 'NativePopup' };
class ComponentBase {}
const Component = loadTypeScript(new URL('../src/features/retrieval/workbench/search-result-panel/log-clustering/components/finger-tools/cluster-filter.tsx', import.meta.url), {
  'tdesign-vue-next': { Popup, Button: {}, Checkbox: {}, Input: {} },
  'vue-property-decorator': { Component: value => value, Prop: () => () => {}, Emit: () => () => {}, Watch: () => () => {} },
  'vue-tsx-support': { Component: ComponentBase },
  './cluster-filter.scss': {},
}, { jsx: ts.JsxEmit.ReactJSX, jsxImportSource: 'vue', experimentalDecorators: true }).default;
function fixture() {
  const toggles = [], selected = [];
  const vm = new Component();
  Object.assign(vm, { title: '标签', searchable: true, popoverMinWidth: 200, select: ['all'], selectList: [{ id: 'all', name: '全部' }, { id: 'cluster-1', name: 'BCS-K8S-26888' }], loading: false, isActive: false, toggle: value => toggles.push(value), $t: value => value });
  vm.handleSelectedOption = value => selected.push(value);
  vm.watchSelectValue(vm.select);
  return { vm, toggles, selected };
}

test('controlled filter accepts outside close, clears keyword and reports one close without submitting', () => {
  const { vm, toggles } = fixture();
  vm.toggleSelect(true);
  vm.keyword = 'draft';
  vm.selectValue = ['cluster-1'];
  const popup = vm.render();
  assert.equal(popup.type, Popup);
  popup.props.onVisibleChange(false);
  assert.equal(vm.isShowSelectOption, false);
  assert.equal(vm.keyword, '');
  assert.deepEqual(toggles, [true, false]);
  assert.deepEqual(vm.select, ['all']);
  popup.props.onVisibleChange(false);
  assert.deepEqual(toggles, [true, false]);
});

test('popup focus inside does not reset draft; search and selected events preserve values', () => {
  const { vm, toggles, selected } = fixture();
  vm.toggleSelect(true);
  vm.keyword = 'k8s';
  vm.selectValue = ['cluster-1'];
  vm.render().props.onVisibleChange(true);
  assert.deepEqual(toggles, [true]);
  assert.equal(vm.keyword, 'k8s');
  assert.deepEqual(vm.getVisibleOptions(), [{ id: 'cluster-1', name: 'BCS-K8S-26888' }]);
  vm.handleOptionChange('cluster-1', false);
  assert.deepEqual(selected, [[]]);
  assert.deepEqual(vm.select, ['all']);
});

test('cancel closes with a copied draft and submit retains original selected payload', () => {
  const { vm, toggles } = fixture();
  vm.toggleSelect(true);
  vm.selectValue = ['cluster-1'];
  vm.cancelFilter();
  assert.deepEqual(vm.selectValue, ['all']);
  assert.notEqual(vm.selectValue, vm.select);
  assert.equal(vm.isShowSelectOption, false);
  vm.select = ['cluster-1'];
  vm.toggleSelect(true);
  assert.deepEqual(vm.submitFilter(), ['cluster-1']);
  assert.deepEqual(toggles, [true, false, true, false]);
});
