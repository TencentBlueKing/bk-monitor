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

import assert from 'node:assert/strict';
import { dirname, resolve } from 'node:path';
import { test } from 'node:test';
import { fileURLToPath } from 'node:url';

import { renderToString } from '@vue/server-renderer';
import { createSSRApp, h } from 'vue';

import { extractContract } from '../../../../../migration-project/migration-engine/extract-contract.mjs';
import { LabelTargetActions } from './label-target-actions.mjs';
import { mapBkButtonProps, mapBkInputProps, mapBkOption, mapBkSelectProps } from './map.mjs';
import { WorkloadTypeSelect } from './workload-type-select.mjs';

const here = dirname(fileURLToPath(import.meta.url));
const webRoot = resolve(here, '../../../../..');
const labelSource = resolve(webRoot, 'src/components/collection-access/components/step-add/label-target-dialog.vue');
const selectSource = resolve(webRoot, 'src/components/collection-access/components/step-add/container-target-item.vue');

test('label dialog contract keeps search input and confirm disabled binding', () => {
  const contract = extractContract(labelSource, 'label-target-dialog');
  const input = contract.controls.find(item => item.tag === 'bk-input');
  const buttons = contract.controls.filter(item => item.tag === 'bk-button');
  assert.equal(input.attrs['v-model'], 'filterStr');
  assert.equal(input.attrs.clearable, true);
  assert.equal(input.events.change, 'search');
  assert.deepEqual(input.unmapped, ['right-icon']);
  assert.equal(buttons[0].attrs.theme, 'primary');
  assert.equal(buttons[0].attrs.type, 'submit');
  assert.equal(buttons[0].attrs[':disabled'], '!isHaveSelectItem');
  assert.equal(buttons[0].events.click, 'handelConfirmLabel');
  assert.equal(buttons[1].attrs.theme, undefined);
  assert.equal(buttons[1].events.click, 'handelCancelDialog');

  const search = mapBkInputProps({
    value: '',
    clearable: input.attrs.clearable === true,
    rightIcon: input.attrs['right-icon'],
  });
  assert.equal(search.props.clearable, true);
  assert.equal(search.props.suffixIcon, undefined);
  assert.deepEqual(search.gaps, ['right-icon']);

  const confirm = mapBkButtonProps({
    theme: buttons[0].attrs.theme,
    disabled: true,
    type: buttons[0].attrs.type,
  });
  assert.equal(confirm.props.theme, 'primary');
  assert.equal(confirm.props.disabled, true);
  assert.equal(confirm.props.type, 'submit');
  assert.equal(confirm.props.variant, undefined);

  const cancel = mapBkButtonProps({});
  assert.equal(cancel.props.theme, 'default');
  assert.equal(cancel.props.variant, 'outline');
  assert.notEqual(cancel.props.theme, 'primary');
});

test('container select contract maps searchable and option id', () => {
  const contract = extractContract(selectSource, 'container-target-item');
  const selects = contract.controls.filter(item => item.tag === 'bk-select');
  const select = selects[0];
  const option = contract.controls.find(item => item.tag === 'bk-option');
  assert.equal(select.attrs['v-model'], 'formData.workload_type');
  assert.equal(select.attrs.searchable, true);
  assert.equal(select.attrs['allow-create'], true);
  assert.equal(select.attrs.clearable, true);
  assert.equal(select.events.toggle, 'closeTitle');
  assert.equal(selects[1].events.toggle, 'status => (isOptionOpen = status)');
  assert.equal(option.attrs[':id'], 'option.id');
  assert.equal(option.attrs[':name'], 'option.name');

  const mapped = mapBkSelectProps({
    value: 'Deployment',
    searchable: true,
    allowCreate: true,
    clearable: true,
  });
  assert.equal(mapped.props.filterable, true);
  assert.equal(mapped.props.creatable, true);
  assert.equal(mapped.props.clearable, true);
  assert.deepEqual(mapBkOption({ id: 'Deployment', name: 'Deployment' }).props, {
    value: 'Deployment',
    label: 'Deployment',
  });
});

test('label target actions render the disabled confirm state', async () => {
  const app = createSSRApp({
    render: () => h(LabelTargetActions, { filterStr: 'app', hasSelection: false }),
  });
  const html = await renderToString(app);
  assert.match(html, /data-testid="label-target-search"/);
  assert.match(html, /data-testid="label-target-confirm"/);
  assert.match(html, /data-testid="label-target-cancel"/);
  assert.match(html, /确定/);
  assert.match(html, /取消/);
  assert.match(html, /disabled/);
  assert.equal((html.match(/t-button--theme-primary/g) || []).length, 1);
  assert.match(html, /t-button--variant-outline/);
});

test('workload type select renders the selected workload id', async () => {
  const app = createSSRApp({
    render: () => h(WorkloadTypeSelect, {
      modelValue: 'Deployment',
      options: [{ id: 'Deployment', name: 'Deployment' }],
    }),
  });
  const html = await renderToString(app);
  assert.match(html, /data-testid="workload-type-select"/);
  assert.match(html, /value="Deployment"/);
});
