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
import * as Vue from 'vue';
import { loadTypeScript } from './helpers/load-typescript.mjs';

const source = path => new URL(`../../web-v2/src/${path}`, import.meta.url);
const target = path => new URL(`../src/${path}`, import.meta.url);
const load = file => loadTypeScript(file, { vue: Vue });
const v2Sort = load(source('hooks/use-list-sort.ts'));
const v3Sort = load(target('shared/composables/use-list-sort.ts'));
const timePath = 'views/manage-v2/log-collection/components/create-operation/log-timezone.ts';
const nativeTimePath = 'features/collection/current/components/create-operation/log-timezone.ts';
const v2Time = load(source(timePath));
const v3Time = load(target(nativeTimePath));

test('master sync: exact business and space IDs precede fuzzy text, with signed IDs ranked correctly', () => {
  const list = [
    { id: 1, bk_biz_id: -793, space_id: 8, space_name: '793 matching', py_text: 'demo', space_uid: 'bkcc__-793' },
    { id: 2, bk_biz_id: 793, space_id: 9, space_name: 'demo', py_text: 'demo', space_uid: 'bkcc__793' },
    { id: 3, bk_biz_id: 45, space_id: 793, space_name: 'space', py_text: 'space', space_uid: 'custom__45' },
    { id: 4, bk_biz_id: 56, space_id: 10, space_name: '793', py_text: 'name', space_uid: 'custom__56' },
  ];
  for (const search of ['', '793', '-793', 'demo', 'BKCC__793', 'space', 'missing']) {
    const results = [v2Sort, v3Sort].map(module => {
      const hook = module.default(list, ['space_name', 'py_text', 'space_uid'], ['bk_biz_id', 'space_id']);
      hook.updateSearchText(search);
      return hook.sortList.value.map(item => item.id);
    });
    assert.deepEqual(results[1], results[0], search);
    if (search === '793') assert.deepEqual(results[1].slice(0, 3), [2, 1, 3]);
  }
  assert.equal(v3Sort.isExactHiddenMatch(list[2], '793', ['space_id']), true);
  assert.equal(v3Sort.isExactSearchFieldMatch(list[3], ' 793 ', ['space_name']), true);
});

test('master sync: timezone parsing and timestamp snapshots follow V2 without mutating templates', () => {
  const zones = [{ id: 0, name: 'UTC' }, { id: 8, name: 'UTC+8' }, { id: -3.5, name: 'UTC-3:30' }];
  for (const value of ['2026-11-12T10:00:00Z', '2026-11-12T10:00:00+0800', '2026-11-12T10:00:00-03:30',
    'bad+25:00', 'bad+08:60', '', null, 123]) {
    assert.deepEqual(v3Time.parseTimeZone(value, zones), v2Time.parseTimeZone(value, zones));
  }
  assert.equal(v3Time.parseTimeZone('2026-11-12T10:00:00+0800', zones).id, 8);
  for (const name of ['ISO8601', 'rfc3339', 'YYYY-MM-DD HH:mm:ssZZ', 'epoch_second', 'YYYY-MM-DD']) {
    assert.equal(v3Time.hasTimeZone({ id: name, name }), v2Time.hasTimeZone({ id: name, name }));
  }
  const input = [{ is_time: true, option: { time_format: 'epoch_micros', time_zone: 8 } },
    { is_time: false, option: { time_format: 'epoch_micros', time_zone: 8 } }];
  const before = structuredClone(input);
  const output = v3Time.normalizeTimestampTimeZones(input);
  assert.deepEqual(output, v2Time.normalizeTimestampTimeZones(input));
  assert.deepEqual(input, before);
  assert.equal(output[0].option.time_zone, 0);
  assert.equal(output[1].option.time_zone, 8);
});

test('master sync: timezone watcher restores parsed offsets, respects templates and resets on format change', async () => {
  async function exercise(module) {
    const scope = Vue.effectScope();
    const form = Vue.ref({ field_name: 'time', time_format: 'iso', time_zone: '', log_reporting_time: false,
      etl_fields: [{ field_name: 'time', value: '2026-11-12T10:00:00+08:00' }] });
    const formats = Vue.ref([{ id: 'iso', name: 'ISO8601' }, { id: 'plain', name: 'YYYY-MM-DD' }]);
    const zones = Vue.ref([{ id: 0, name: 'UTC' }, { id: 8, name: 'UTC+8' }]);
    const bound = Vue.ref(false);
    const hook = scope.run(() => module.useLogTimeZone(form, formats, zones, bound));
    try {
      assert.equal(hook.isTimeZoneLocked.value, true);
      form.value.time_zone = 0;
      await Vue.nextTick();
      assert.equal(form.value.time_zone, 8);
      bound.value = true;
      await Vue.nextTick();
      form.value.time_zone = 0;
      await Vue.nextTick();
      assert.equal(form.value.time_zone, 0);
      bound.value = false;
      await Vue.nextTick();
      hook.changeTimeFormat('epoch_millis');
      await Vue.nextTick();
      assert.equal(form.value.time_zone, 0);
      assert.equal(hook.isTimestamp.value, true);
      hook.changeTimeFormat('plain');
      await Vue.nextTick();
      assert.equal(form.value.time_zone, '');
      return Vue.toRaw(form.value);
    } finally { scope.stop(); }
  }
  assert.deepEqual(await exercise(v3Time), await exercise(v2Time));
});

test('master sync: scenario CSS namespace and table column refresh are preserved in V3', () => {
  const panel = readFileSync(target('features/retrieval/workspace/search-bar/scene-filter/filter-panel.tsx'), 'utf8');
  assert.equal((panel.match(/\['scene-filter-field-input'/g) ?? []).length, 2);
  const fields = readFileSync(target('features/retrieval/workbench/result-comp/update/fields-setting.vue'), 'utf8');
  assert.match(fields, /updateIsSetDefaultTableColumn'\);\s*RetrieveHelper\.fire\(RetrieveEvent\.VISIBLE_FIELD_COLUMN_LAYOUT_CHANGE\)/);
  const grok = readFileSync(target('features/grok/current/components/grok-input.tsx'), 'utf8');
  assert.match(grok, /getReferenceClientRect:/);
  assert.match(grok, /name: 'grokMaxHeight'/);
  assert.doesNotMatch(grok, /zIndex: 9999/);
});
