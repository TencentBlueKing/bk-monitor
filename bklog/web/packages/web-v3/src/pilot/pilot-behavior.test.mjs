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
import { test } from 'node:test';

import {
  applyLabelResponse,
  cancelDialog,
  confirmLabel,
  createLabelTargetState,
  filterTreeNode,
  finishLabelRequest,
  isHaveSelectItem,
  onDialogHide,
  onDialogShow,
  selectTreeItem,
  buildNodeLabelQuery,
} from './label-target-state.mjs';
import {
  buildWorkloadQuery,
  changeWorkloadType,
  createWorkloadState,
  destroyWorkload,
  settleWorkloadResponse,
} from './workload-target-state.mjs';

function ids() {
  let next = 1;
  return () => `id-${next++}`;
}

test('confirm stays disabled until a label id is selected', () => {
  const state = createLabelTargetState();
  assert.equal(isHaveSelectItem(state), false);
  state.matchSelectItemList = [{ id: 'a', key: 'app', value: 'nginx', operator: '=' }];
  assert.equal(isHaveSelectItem(state), false);
  state.matchSelectList = ['a'];
  assert.equal(isHaveSelectItem(state), true);
});

test('confirm emits only checked ids and clears both lists', () => {
  const state = createLabelTargetState();
  state.matchSelectList = ['a'];
  state.matchSelectItemList = [
    { id: 'a', key: 'app', value: 'nginx', operator: '=' },
    { id: 'b', key: 'app', value: 'skip', operator: '=' },
  ];
  state.matchCheckedList = ['c'];
  state.matchCheckedItemList = [{ id: 'c', key: 'tier', value: 'prod', operator: '!=' }];
  const result = confirmLabel(state);
  assert.deepEqual(result.labelSelector, [
    { id: 'a', key: 'app', value: 'nginx', operator: '=', type: 'match_labels' },
    { id: 'c', key: 'tier', value: 'prod', operator: '!=', type: 'match_expressions' },
  ]);
  assert.equal(isHaveSelectItem(state), false);
  assert.deepEqual(state.matchSelectItemList, []);
});

test('cancel resets the selection and does not build a label payload', () => {
  const state = createLabelTargetState();
  state.filterStr = 'app';
  state.matchCheckedList = ['a'];
  state.matchCheckedItemList = [{ id: 'a', key: 'app', value: 'nginx', operator: '=' }];
  cancelDialog(state);
  assert.deepEqual(state.matchCheckedList, []);
  assert.equal(state.filterStr, 'app');
  onDialogHide(state);
  assert.equal(state.filterStr, '');
});

test('opening the dialog copies existing selectors and omits wildcard namespace', () => {
  const state = createLabelTargetState();
  const params = onDialogShow(state, {
    bk_biz_id: 2,
    bcs_cluster_id: 'BCS-1',
    type: 'pod',
    namespaceStr: '*',
    namespacesExclude: '=',
    labelSelector: [{ key: 'app', value: 'nginx', operator: '=' }],
  }, ids());
  assert.deepEqual(params, {
    bk_biz_id: 2,
    bcs_cluster_id: 'BCS-1',
    type: 'pod',
    namespace: undefined,
  });
  assert.equal(state.matchCheckedList[0], 'id-1');
  assert.equal(isHaveSelectItem(state), true);
});

test('node label query drops namespace and stale responses are ignored', () => {
  const state = createLabelTargetState();
  const ignored = selectTreeItem(state, { data: { type: 'namespace' } });
  assert.equal(ignored.shouldRequest, false);
  assert.equal(state.labelLoading, false);
  const started = selectTreeItem(state, { data: { type: 'node' } });
  assert.equal(started.shouldRequest, true);
  assert.equal(state.labelLoading, true);
  const query = buildNodeLabelQuery({
    nameSpaceStr: 'ns',
    nameStr: 'node-a',
    bkBizId: 2,
    bcsClusterId: 'BCS-1',
    type: 'node',
  });
  assert.equal(query.namespace, undefined);
  assert.equal(applyLabelResponse(state, started.requestId - 1, {
    code: 0,
    data: [{ key: 'old', value: '1' }],
  }, [], ids()), false);
  assert.equal(applyLabelResponse(state, started.requestId, {
    code: 0,
    data: [
      { key: 'app', value: 'nginx' },
      { key: 'kept', value: '1' },
    ],
  }, [{ key: 'app', value: 'nginx', operator: '=' }], ids()), true);
  assert.deepEqual(state.matchSelectItemList.map(item => item.key), ['kept']);
  finishLabelRequest(state, started.requestId);
  assert.equal(state.labelLoading, false);
});

test('tree search matches the node name substring', () => {
  assert.equal(filterTreeNode('ng', { data: { name: 'nginx' } }), true);
  assert.equal(filterTreeNode('redis', { data: { name: 'nginx' } }), false);
});

test('workload type outside the known list does not request names', () => {
  const state = createWorkloadState();
  const custom = changeWorkloadType(state, 'custom-type', [{ id: 'Deployment', name: 'Deployment' }]);
  assert.equal(custom.shouldRequest, false);
  assert.equal(state.nameCannotClick, false);
  assert.deepEqual(state.nameList, []);
});

test('known workload type requests names and ignores a stale response', () => {
  const state = createWorkloadState();
  const started = changeWorkloadType(state, 'Deployment', [{ id: 'Deployment', name: 'Deployment' }]);
  assert.equal(started.shouldRequest, true);
  assert.equal(state.nameCannotClick, true);
  const query = buildWorkloadQuery({
    type: 'Deployment',
    bkBizId: 2,
    namespaceStr: '*',
    namespacesExclude: '=',
    bcsClusterId: 'BCS-1',
  });
  assert.deepEqual(query, { type: 'Deployment', bk_biz_id: 2, bcs_cluster_id: 'BCS-1' });
  const excluded = buildWorkloadQuery({
    type: 'Deployment',
    bkBizId: 2,
    namespaceStr: 'kube-system',
    namespacesExclude: '!=',
    bcsClusterId: 'BCS-1',
  });
  assert.equal(excluded.namespaces_exclude, 'kube-system');
  assert.equal(excluded.namespace, undefined);
  settleWorkloadResponse(state, started.requestId - 1, { code: 0, data: ['old'] });
  assert.deepEqual(state.nameList, []);
  assert.equal(state.nameCannotClick, true);
  destroyWorkload(state);
  settleWorkloadResponse(state, started.requestId, { code: 0, data: ['late'] });
  assert.deepEqual(state.nameList, []);
});
