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

import { CollectionController } from './collection-controller.ts';

describe('CollectionController', () => {
  it('AC-001 filters by scenario and status', () => {
    const controller = new CollectionController();
    controller.setScenario('linux');
    controller.setStatus('failed');
    assert.deepEqual(controller.getVisibleItems().map(item => item.id), ['col-2']);
  });

  it('AC-002 start and stop only from allowed states', () => {
    const controller = new CollectionController();
    assert.equal(controller.start('col-1').uiState, 'error');
    assert.equal(controller.stop('col-1').items.find(item => item.id === 'col-1')?.status, 'stopped');
    assert.equal(controller.start('col-1').items.find(item => item.id === 'col-1')?.status, 'running');
  });

  it('AC-003 wizard requires scenario, name/path and cluster', () => {
    const controller = new CollectionController();
    controller.openWizard();
    assert.equal(controller.nextStep().error, 'scenario is required');
    controller.patchDraft({ scenario: 'linux' });
    controller.nextStep();
    assert.equal(controller.nextStep().error, 'name is required');
    controller.patchDraft({ name: 'host-new', path: '/var/log/app.log' });
    controller.nextStep();
    controller.nextStep();
    assert.equal(controller.submitWizard().error, 'cluster is required');
    controller.patchDraft({ cluster: 'es-default' });
    const state = controller.submitWizard();
    assert.equal(state.uiState, 'idle');
    assert.ok(state.items.some(item => item.name === 'host-new' && item.status === 'pending'));
  });
});
