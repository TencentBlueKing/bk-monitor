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
import * as Vue from 'vue';
import ts from 'typescript';
import { loadTypeScript } from './helpers/load-typescript.mjs';

function fixture(configured) {
  const requests = [], confirmations = [], emitted = [];
  const Popup = { name: 'NativePopup' };
  const { default: component } = loadTypeScript(new URL('../src/features/retrieval/workspace/search-result/log-clustering/top-operation/strategy/config-item/index.tsx', import.meta.url), {
    '@/platform/ui/feedback': { TDesignMessage() {} },
    '@/platform/services': { ServicesInstance: { retrieve: { deleteClusteringInfo: async request => { requests.push(request); return { code: 0 }; } } } },
    '@/shared/utils/typed-record': { asDictionary: x => x },
    vue: Vue, 'tdesign-vue-next': { Popup, MessagePlugin() {} },
    '@/shared/composables/use-locale': () => ({ t: x => x }),
    '../edit-strategy/index': {},
    '@/platform/compat/tdesign/info-box': { bkInfoBox: options => confirmations.push(options) },
    '../index': { StrategyType: { NEW_CLASS: 'new_cls_strategy', SUDDEN_INCREASE: 'normal_strategy' } },
    './index.scss': {},
  }, { jsx: ts.JsxEmit.ReactJSX, jsxImportSource: 'vue' });
  const props = { configured, type: 'normal_strategy', indexId: '16176', bkBizId: '5000140', labelName: ['source-label'], configData: { strategy_id: 12 } };
  const render = component.setup(props, { emit: (...args) => emitted.push(args) });
  const tree = () => render(Vue.h);
  const popup = tree().children.find(n => n.type === Popup);
  return { props, tree, popup, requests, confirmations, emitted, menu: popup.props['v-slots'].content().children[0] };
}

test('configured clustering menu retains edit/view/delete actions and deletes only after confirmation', async () => {
  const f = fixture(true);
  assert.equal(f.popup.props.trigger, 'hover');
  assert.equal(f.popup.props.placement, 'bottom-right');
  assert.equal(f.popup.props.overlayClassName, 'clustering-strategy-operation-popup');
  const items = f.menu.children;
  assert.deepEqual(items.map(n => n.children[1].children), ['编辑策略', '查看策略', '删除策略']);
  items[0].props.onClick();
  assert.equal(f.tree().children.at(-1).props.isEdit, true);
  assert.equal(f.tree().children.at(-1).props.isShow, true);
  const previous = globalThis.window;
  const opened = [];
  globalThis.window = { MONITOR_URL: 'https://monitor.example', open: (...args) => opened.push(args) };
  try { items[1].props.onClick(); } finally { globalThis.window = previous; }
  assert.deepEqual(opened, [['https://monitor.example/?bizId=5000140#/strategy-config?strategyLabels=["source-label"]', '_blank', 'noopener,noreferrer']]);
  items[2].props.onClick();
  assert.equal(f.requests.length, 0);
  assert.equal(f.confirmations[0].theme, 'danger');
  await f.confirmations[0].confirmFn();
  assert.deepEqual(f.requests, [{ params: { index_set_id: '16176' }, data: { strategy_type: 'normal_strategy' } }]);
  assert.deepEqual(f.emitted, [['refresh-strategy-info']]);
});

test('unconfigured clustering menu retains create-only action without writes', () => {
  const f = fixture(false);
  const item = f.menu.children[0];
  assert.equal(item.children[1].children, '新建策略');
  item.props.onClick();
  assert.equal(f.tree().children.at(-1).props.isShow, true);
  assert.equal(f.tree().children.at(-1).props.isEdit, false);
  assert.equal(f.requests.length, 0);
});
