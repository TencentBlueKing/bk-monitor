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
const controls = Object.fromEntries(
  ['RadioGroup', 'Radio', 'Select', 'Popconfirm', 'Button'].map((name) => [name, { name }]),
);
const component = loadTypeScript(
  new URL(
    '../src/features/retrieval/workspace/search-result/log-clustering/top-operation/cluster-config/edit-config/rule-operate/index.tsx',
    import.meta.url,
  ),
  {
    'tdesign-vue-next': { ...controls, MessagePlugin() {} },
    '@/platform/services': {
      ServicesInstance: {
        logClustering: {
          ruleTemplate: async () => ({ data: [{ id: 7, template_name: 'system', predefined_varibles: 'encoded' }] }),
        },
      },
    },
    '@/features/index-sets/import-from-other/index': {},
    '@/shared/composables/use-locale': () => ({ t: (x) => x }),
    '@/shared/composables/use-store': () => ({ state: { spaceUid: 'space' } }),
    'vue-router': { useRouter: () => ({ resolve: () => ({ href: '/template' }) }) },
    './util': { base64ToRuleArr: () => [{ NUMBER: 'regex' }] },
    './index.scss': {},
  },
  { jsx: ts.JsxEmit.ReactJSX, jsxImportSource: 'vue' },
).default;
test('native clustering confirmation retains draft mode until confirm and resists trigger-close race', async () => {
  const scope = Vue.effectScope(),
    events = [];
  let exposed;
  const render = scope.run(() =>
    component.setup(
      {
        defaultValue: { regex_rule_type: 'template', regex_template_id: 7, predefined_varibles: 'encoded' },
        ruleList: [{ NUMBER: 'regex' }],
        templateSpaceUid: 'space',
        isExternal: false,
      },
      { emit: (...args) => events.push(args), expose: (value) => (exposed = value) },
    ),
  );
  try {
    await Vue.nextTick();
    await Vue.nextTick();
    events.length = 0;
    const popup = () => render().children[0],
      group = () => popup().children[0];
    assert.equal(popup().type.name, 'Popconfirm');
    assert.equal(exposed.getRuleInfo().type, 'template');
    group().props.onChange('customize');
    await Vue.nextTick();
    assert.equal(group().props.value, 'template');
    assert.equal(popup().props.visible, true);
    assert.deepEqual(events, []);
    popup().props.onVisibleChange(false, { trigger: 'trigger-element-click' });
    assert.equal(popup().props.visible, true);
    popup().props.onCancel();
    assert.equal(popup().props.visible, false);
    assert.equal(exposed.getRuleInfo().type, 'template');
    assert.deepEqual(events, []);
    group().props.onChange('customize');
    await Vue.nextTick();
    popup().props.onConfirm();
    assert.equal(popup().props.visible, false);
    assert.equal(exposed.getRuleInfo().type, 'customize');
    assert.deepEqual(events, [
      ['rule-type-change', 'customize'],
      ['rule-list-change', []],
    ]);
  } finally {
    scope.stop();
  }
});

test('native template unbind keeps mode and rules on cancel, then detaches only the draft on confirm', async () => {
  const scope = Vue.effectScope(),
    events = [];
  let exposed;
  const render = scope.run(() =>
    component.setup(
      {
        defaultValue: { regex_rule_type: 'template', regex_template_id: 7, predefined_varibles: 'encoded' },
        ruleList: [{ NUMBER: 'regex' }],
        templateSpaceUid: 'space',
        isExternal: false,
      },
      { emit: (...args) => events.push(args), expose: (value) => (exposed = value) },
    ),
  );
  try {
    await Vue.nextTick();
    await Vue.nextTick();
    events.length = 0;
    const popup = () => render().children[1].children[0].children.find((node) => node?.type?.name === 'Popconfirm');
    assert.ok(popup());
    assert.equal(popup().props.confirmBtn.content, '解绑');
    assert.equal(popup().props.popupProps.overlayInnerStyle.width, '380px');
    popup().props.onVisibleChange(true);
    popup().props.onCancel();
    assert.equal(popup().props.visible, false);
    assert.deepEqual(events, []);
    assert.deepEqual(exposed.getRuleInfo(), { type: 'template', id: 7 });
    popup().props.onVisibleChange(true);
    popup().props.onConfirm();
    assert.equal(exposed.getRuleInfo().type, 'customize');
    assert.deepEqual(events, [
      ['rule-type-change', 'customize'],
      ['rule-list-change', [{ NUMBER: 'regex' }]],
      ['unbind-template'],
    ]);
  } finally {
    scope.stop();
  }
});
