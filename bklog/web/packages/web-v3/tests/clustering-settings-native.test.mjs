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
import { readFileSync } from 'node:fs';
import ts from 'typescript';
const source = readFileSync(
  new URL(
    '../src/features/retrieval/workspace/search-result/log-clustering/top-operation/cluster-config/edit-config/index.tsx',
    import.meta.url,
  ),
  'utf8',
);
function handler(name, dependencies) {
  const ast = ts.createSourceFile('settings.tsx', source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  let body;
  function visit(node) {
    if (ts.isVariableDeclaration(node) && node.name.getText(ast) === name) body = node.initializer.getText(ast);
    ts.forEachChild(node, visit);
  }
  visit(ast);
  assert.ok(body);
  const code = ts.transpile('return ' + body, {
    target: ts.ScriptTarget.ES2022,
  });
  return new Function(...Object.keys(dependencies), code)(...Object.values(dependencies));
}
async function fixture(validation, serviceError = false) {
  const calls = [],
    loading = [],
    events = [];
  const form = {
    clustering_fields: 'log',
    max_dist_list: '0.5',
    max_log_length: 1000,
    filter_rules: [
      {
        field_name: 'path',
        logic_operator: 'and',
        op: '=',
        value: ['/var/log/app'],
      },
    ],
  };
  const submit = handler('handleSubmit', {
    formRef: { value: { validate: async () => validation } },
    formData: { value: form },
    indexSetItem: { value: { index_set_id: 16176, bk_biz_id: 5000140 } },
    configId: { value: 123 },
    ruleConfigOperateRef: {
      value: { setSaveLoading: (value) => loading.push(value) },
    },
    ruleOperateRef: {
      value: { getRuleInfo: () => ({ type: 'template', id: 8 }) },
    },
    ruleTableRef: { value: { getRuleListBase64: () => 'fixture-base64' } },
    ServicesInstance: {
      retrieve: {
        updateClusteringConfig: async (options) => {
          calls.push(options);
          if (serviceError) throw new Error('fixture failure');
        },
      },
    },
    NotifyPlugin: { info: (message) => events.push(message.title) },
    t: (text) => text,
    emit: (...args) => events.push(args),
  });
  submit();
  await new Promise((resolve) => setImmediate(resolve));
  return { calls, loading, events };
}
test('clustering native form rejects all non-true validation results without submitting', async () => {
  for (const result of [false, undefined, { clustering_fields: [{ message: 'required' }] }]) {
    const f = await fixture(result);
    assert.deepEqual(f.calls, []);
    assert.deepEqual(f.loading, [false]);
    assert.deepEqual(f.events, []);
  }
});
test('clustering native form retains full V2 save payload and closes only after service success', async () => {
  const f = await fixture(true);
  assert.deepEqual(f.calls, [
    {
      params: { index_set_id: 16176 },
      data: {
        max_dist_list: '0.5',
        predefined_varibles: 'fixture-base64',
        max_log_length: 1000,
        clustering_fields: 'log',
        filter_rules: [
          {
            fields_name: 'path',
            logic_operator: 'and',
            op: '=',
            value: ['/var/log/app'],
          },
        ],
        regex_rule_type: 'template',
        regex_template_id: 8,
        signature_enable: true,
        collector_config_id: 123,
        index_set_id: 16176,
        bk_biz_id: 5000140,
      },
    },
  ]);
  assert.equal(f.events.length, 2);
  assert.deepEqual(f.events[1], ['close']);
  assert.deepEqual(f.loading, [false]);
});
test('clustering settings use native vertical labels with trailing required markers and source numeric bounds', () => {
  assert.match(source, /labelAlign=['"]top['"]/);
  assert.match(source, /requiredMarkPosition=['"]right['"]/);
  assert.ok(source.includes('decimalPlaces={0}'));
  assert.ok(source.includes('max={2000000}'));
  assert.ok(source.includes('min={1}'));
  assert.doesNotMatch(source, /<bk-(form|form-item|input|select|option)\b/);
  const wrapper = readFileSync(
    new URL(
      '../src/features/retrieval/workspace/search-result/log-clustering/top-operation/cluster-config/index.tsx',
      import.meta.url,
    ),
    'utf8',
  );
  assert.match(wrapper, /<TDrawer/);
  assert.ok(wrapper.includes('onClose={handleBeforeClose}'));
  assert.ok(wrapper.includes('onClick={handleBeforeClose}'));
});

test('clustering save failure restores loading without success or close events', async () => {
  const f = await fixture(true, true);
  assert.equal(f.calls.length, 1);
  assert.deepEqual(f.events, []);
  assert.deepEqual(f.loading, [false]);
});
