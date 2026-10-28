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
import { describe, it } from 'node:test';

import { ManageModuleController, MANAGE_PAGE_SPECS } from './manage-module.ts';

describe('ManageModuleController', () => {
  it('AC-001 index set and clean keep dedicated tabs', () => {
    assert.deepEqual(MANAGE_PAGE_SPECS['manage-index-set'].tabs.map(item => item.title), ['列表', '脱敏']);
    assert.deepEqual(MANAGE_PAGE_SPECS['manage-clean'].tabs.map(item => item.title), ['清洗项', '模板', '脱敏']);
    assert.deepEqual(MANAGE_PAGE_SPECS['manage-archive'].tabs.map(item => item.title), ['仓库', '列表', '回溯']);
  });

  it('AC-002 tab switch loads that tab dataset', () => {
    const controller = new ManageModuleController('manage-clean');
    controller.setTab('masking');
    assert.equal(controller.getState().tab, 'masking');
    assert.equal(controller.getVisibleItems()[0].name, 'phone / password');
  });

  it('AC-003 save appends and rejects blank names', () => {
    const controller = new ManageModuleController('manage-index-set');
    assert.equal(controller.save('').items.length, 2);
    assert.equal(controller.save('biz-index').items[0].name, 'biz-index');
  });
});
