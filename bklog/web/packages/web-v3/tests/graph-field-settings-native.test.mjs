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
import { loadScriptSetup } from './helpers/load-script-setup.mjs';
import { baselineUrl } from '../tools/source-baseline.mjs';
const file = new URL(
  '../src/features/retrieval/workbench/search-result-panel/graph-analysis/common/field-settings.vue',
  import.meta.url,
);
const source = baselineUrl('views/retrieve-v2/search-result-panel/graph-analysis/common/field-settings.vue');
function fixture(file, options) {
  const events = [];
  const component = loadScriptSetup(file, {
    h: Vue.h,
    TTooltip: { name: 'Tooltip' },
    useLocale: () => ({ t: (key) => key }),
  });
  const props = Vue.reactive({
    options,
    resultSchema: [
      { field_alias: 'minute1', field_type: 'string' },
      { field_alias: 'log_count', field_type: 'long' },
      { field_alias: 'host', field_type: 'keyword' },
    ],
  });
  return { props, events, model: component.setup(props, { expose() {}, emit: (...args) => events.push(args) }) };
}
const options = () => ({
  xFields: ['minute1'],
  yFields: ['log_count'],
  dimensions: [],
  hiddenFields: [],
  category: 'line',
});
test('native graph selectors preserve V2 field exclusions, numeric metrics and current selections', () => {
  const before = fixture(source, options()),
    after = fixture(file, options());
  for (const key of ['xFieldOptions', 'yFieldOptions', 'dimensionsOptions'])
    assert.deepEqual(
      after.model[key].value.map((row) => ({ id: row.value, disabled: row.disabled })),
      before.model[key].value.map((row) => ({ id: row.item, disabled: row.disabled })),
    );
  assert.deepEqual(
    after.model.yFieldOptions.value.map((row) => row.value),
    ['log_count'],
  );
  after.props.options.xFields = [];
  after.props.options.dimensions = ['minute1'];
  assert.deepEqual(
    after.model.xFieldOptions.value.map((row) => row.value),
    ['host'],
  );
  assert.ok(after.model.dimensionsOptions.value.some((row) => row.value === 'minute1'));
});
test('selector changes retain V2 axis and value payloads without changing parent drafts', () => {
  const f = fixture(file, options());
  for (const [axis, value] of [
    ['yFields', ['log_count']],
    ['xFields', ['host']],
    ['dimensions', 'minute1'],
    ['hiddenFields', []],
  ]) {
    f.model.change(axis, value);
    assert.deepEqual(f.events.at(-1), ['update', axis, value]);
  }
  assert.deepEqual(f.props.options, options());
});
test('hidden-field choices preserve the V2 last-visible-field guard and its tooltip', () => {
  const f = fixture(file, { ...options(), category: 'table', hiddenFields: ['host', 'minute1'] });
  let rows = f.model.hiddenFieldOptions.value;
  assert.equal(rows.find((row) => row.value === 'log_count').disabled, true);
  assert.equal(rows.find((row) => row.value === 'host').disabled, false);
  assert.equal(rows.find((row) => row.value === 'log_count').content().props.content, '至少需要一个字段');
  f.props.options.hiddenFields = ['host'];
  rows = f.model.hiddenFieldOptions.value;
  assert.equal(
    rows.some((row) => row.disabled),
    false,
  );
});
