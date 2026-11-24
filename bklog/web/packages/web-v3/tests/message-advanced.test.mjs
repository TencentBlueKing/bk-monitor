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

const advancedSource = readFileSync(new URL('../src/shared/lib/advanced-message.tsx', import.meta.url), 'utf8');
const messageSource = readFileSync(new URL('../src/shared/lib/message.ts', import.meta.url), 'utf8');
const compatSource = readFileSync(
  new URL('../src/platform/compat/tdesign/bkui-vue.ts', import.meta.url),
  'utf8',
);

function extractFunction(source, name) {
  const ast = ts.createSourceFile('fixture.tsx', source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  let body;
  function visit(node) {
    if (ts.isFunctionDeclaration(node) && node.name?.getText(ast) === name) body = node.getText(ast);
    ts.forEachChild(node, visit);
  }
  visit(ast);
  assert.ok(body, `${name} should exist`);
  const code = ts.transpile(body.replace(/^export\s+/, ''), {
    target: ts.ScriptTarget.ES2022,
    module: ts.ModuleKind.CommonJS,
  });
  return new Function('isVNode', `${code}; return ${name};`)((value) => Boolean(value?.__vnode));
}

test('isAdvancedMessage only accepts bkui advanced message objects', () => {
  const isAdvancedMessage = extractFunction(advancedSource, 'isAdvancedMessage');
  assert.equal(isAdvancedMessage({ code: 'E100', overview: 'synthetic overview' }), true);
  assert.equal(isAdvancedMessage({ details: { field: 'value' } }), true);
  assert.equal(isAdvancedMessage({ suggestion: 'synthetic suggestion' }), true);
  assert.equal(isAdvancedMessage('plain text'), false);
  assert.equal(isAdvancedMessage(null), false);
  assert.equal(isAdvancedMessage([{ overview: 'nested' }]), false);
  assert.equal(isAdvancedMessage({ __vnode: true, overview: 'vnode' }), false);
  assert.equal(isAdvancedMessage({ unrelated: true }), false);
});

test('advanced message retains bkui geometry, delay and tool order contracts', () => {
  assert.match(advancedSource, /const ADVANCED_WIDTH = 800/);
  assert.match(advancedSource, /const ADVANCED_DELAY = 8000/);
  assert.match(advancedSource, /const SINGLE_LINE_DELAY = 3000/);
  assert.match(advancedSource, /const ACTION_ORDER = \['assistant', 'details', 'fix', 'close'\]/);
  assert.match(advancedSource, /event\.altKey && event\.keyCode === 80/);
  assert.match(advancedSource, /message\.type === 'key-value'/);
  assert.match(advancedSource, /stringifyDetails\(details\)/);
  assert.match(advancedSource, /bk\.message\.assistant/);
  assert.match(advancedSource, /bk\.message\.details/);
  assert.match(advancedSource, /bk\.message\.copySuccess/);
  assert.match(advancedSource, /onMouseenter=\{clearTimer\}/);
  assert.match(advancedSource, /onMouseleave=\{startTimer\}/);
});

test('message entry routes advanced objects away from plain TDesign content', () => {
  assert.match(messageSource, /if \(isAdvancedMessage\(message\)\) \{\s+return showAdvancedMessage/);
  assert.match(messageSource, /export const showMessage/);
  assert.match(messageSource, /export const showNotify = showMessage/);
  assert.match(compatSource, /isAdvancedMessage\(options\.message\) \|\| options\.actions/);
  assert.match(compatSource, /showAdvancedMessage\(/);
  // 高级对象必须在普通 MessagePlugin 文本路径之前分流，避免被 String() 压平。
  assert.ok(
    compatSource.indexOf('isAdvancedMessage(options.message)') <
      compatSource.indexOf("MessagePlugin[theme]({ content: contentOf(options)"),
  );
});

test('collection table keeps V2 header, pagination and toolbar density', () => {
  for (const file of ['table-list-v1.scss', 'table-list-v2.scss']) {
    const scss = readFileSync(
      new URL(`../src/features/collection/current/components/list-main/table-list/${file}`, import.meta.url),
      'utf8',
    );
    assert.match(scss, /\.t-table__header th \{\s+font-size: var\(--bklog-font-action, 14px\);\s+line-height: 22px;/);
    assert.match(scss, /\.t-table__body tr \{\s+line-height: 22px;/);
    assert.match(scss, /\.t-input,\s+\.t-select-input \{\s+font-size: var\(--bklog-font-action, 14px\);/);
  }
});
