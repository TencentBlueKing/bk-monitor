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

import { mkdirSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..', '.ai-native', 'specs');

const shared = {
  data: {
    id: 'data.resource-item',
    version: '0.1.0',
    title: '管理资源项',
    source: 'Vue3 local catalog, not inferred from Vue2 v1',
    fields: [
      { name: 'id', type: 'string', required: true, meaning: '资源 ID' },
      { name: 'name', type: 'string', required: true, meaning: '名称' },
      { name: 'status', type: 'string', required: true, meaning: '状态' },
      { name: 'keyword', type: 'string', required: false, nullable: true, meaning: '检索关键字' },
    ],
  },
  state: {
    id: 'state.resource-list',
    owner: 'ResourceListController',
    readers: ['ResourceListPage'],
    writers: ['ResourceListController'],
    initial: 'idle',
    cleanup: 'none',
    concurrency: 'single writer',
    transitions: [
      { from: 'idle', event: 'FILTER', to: 'filtered' },
      { from: 'filtered', event: 'SAVE_FAIL', to: 'error' },
      { from: 'error', event: 'SAVE_OK', to: 'idle' },
    ],
  },
  ui: {
    id: 'ui.resource-list',
    component: 'ResourceListPage',
    states: ['idle', 'filtered', 'error'],
    transitions: [
      { from: 'idle', event: 'FILTER', to: 'filtered' },
      { from: 'filtered', event: 'SAVE_FAIL', to: 'error' },
    ],
  },
  action: {
    id: 'action.mutate-resource',
    title: '新增或更新资源',
    inputs: ['name', 'status'],
    preconditions: ['name after trim is unique'],
    permission: 'manage.write',
    idempotent: false,
    sideEffects: ['update resource catalog'],
    failure: 'duplicate or empty name sets error',
  },
};

const modules = [
  ['retrieve-clustering', '日志聚类', '按模式聚合当前检索结果'],
  ['retrieve-template', '检索模板', '管理检索模板列表'],
  ['retrieve-context', '上下文日志', '围绕锚点行展开前后日志'],
  ['retrieve-realtime', '实时日志', '流式追加并限制缓冲'],
  ['manage-collection', '采集项', '管理日志采集项'],
  ['manage-clean', '清洗模板', '管理清洗模板'],
  ['manage-extract', '日志提取', '管理提取任务与链路'],
  ['manage-archive', '日志归档', '管理归档仓库与回溯'],
  ['manage-es', 'ES 集群', '管理存储集群'],
  ['manage-grok', 'Grok 管理', '管理 Grok 规则'],
  ['manage-client-log', '客户端日志采集', '管理客户端采集部署'],
  ['client-log-search', '客户端日志检索', '按任务检索客户端日志'],
  ['extract', '提取任务中心', '提交并跟踪提取任务'],
  ['dashboard', '仪表盘', '浏览日志仪表盘'],
  ['authorization', '授权管理', '管理授权策略'],
  ['share', '分享链接', '管理检索分享'],
  ['data-id-url', '数据 ID 链接', '管理数据 ID 跳转'],
];

const specialContracts = {
  'retrieve-clustering': {
    state: {
      id: 'state.retrieve-clustering',
      owner: 'ClusteringController',
      readers: ['ClusteringPage'],
      writers: ['ClusteringController'],
      initial: 'idle',
      cleanup: 'none',
      concurrency: 'single writer',
      transitions: [
        { from: 'idle', event: 'GROUP', to: 'success' },
        { from: 'success', event: 'FILTER', to: 'filtered' },
      ],
    },
    ui: {
      id: 'ui.retrieve-clustering',
      component: 'ClusteringPage',
      states: ['idle', 'success', 'filtered'],
      transitions: [
        { from: 'idle', event: 'GROUP', to: 'success' },
        { from: 'success', event: 'FILTER', to: 'filtered' },
      ],
    },
    action: {
      id: 'action.group-clusters',
      title: '按模式聚类',
      inputs: ['records', 'query'],
      preconditions: ['records is an array'],
      permission: 'retrieve.search',
      idempotent: true,
      sideEffects: ['derive cluster groups'],
      failure: 'empty records yield empty groups',
    },
  },
  'retrieve-context': {
    state: {
      id: 'state.retrieve-context',
      owner: 'ContextController',
      readers: ['ContextPage'],
      writers: ['ContextController'],
      initial: 'idle',
      cleanup: 'drop neighbors on newer open',
      concurrency: 'latest open wins',
      transitions: [
        { from: 'idle', event: 'SEARCHING', to: 'waiting' },
        { from: 'idle', event: 'OPEN_OK', to: 'success' },
        { from: 'idle', event: 'OPEN_MISS', to: 'empty' },
      ],
    },
    ui: {
      id: 'ui.retrieve-context',
      component: 'ContextPage',
      states: ['idle', 'waiting', 'success', 'empty'],
      transitions: [
        { from: 'idle', event: 'SEARCHING', to: 'waiting' },
        { from: 'idle', event: 'OPEN_OK', to: 'success' },
      ],
    },
    action: {
      id: 'action.open-context',
      title: '打开上下文',
      inputs: ['records', 'anchorId', 'isSearching', 'windowSize'],
      preconditions: ['anchorId is provided'],
      permission: 'retrieve.search',
      idempotent: true,
      sideEffects: ['slice neighbors around the anchor'],
      failure: 'missing anchor yields empty',
    },
  },
  'retrieve-realtime': {
    state: {
      id: 'state.retrieve-realtime',
      owner: 'RealtimeController',
      readers: ['RealtimePage'],
      writers: ['RealtimeController'],
      initial: 'idle',
      cleanup: 'stop streaming on leave',
      concurrency: 'single writer',
      transitions: [
        { from: 'idle', event: 'START', to: 'streaming' },
        { from: 'streaming', event: 'STOP', to: 'stopped' },
      ],
    },
    ui: {
      id: 'ui.retrieve-realtime',
      component: 'RealtimePage',
      states: ['idle', 'streaming', 'stopped'],
      transitions: [
        { from: 'idle', event: 'START', to: 'streaming' },
        { from: 'streaming', event: 'STOP', to: 'stopped' },
      ],
    },
    action: {
      id: 'action.append-realtime',
      title: '追加实时日志',
      inputs: ['record'],
      preconditions: ['controller is streaming'],
      permission: 'retrieve.search',
      idempotent: false,
      sideEffects: ['append and cap buffer'],
      failure: 'append before start is ignored',
    },
  },
};

function write(kind, name, data) {
  const dir = join(root, kind);
  mkdirSync(dir, { recursive: true });
  writeFileSync(join(dir, `${name}.json`), `${JSON.stringify(data, null, 2)}\n`);
}

write('data', 'resource-item', shared.data);
write('state', 'resource-list', shared.state);
write('ui', 'resource-list', shared.ui);
write('actions', 'mutate-resource', shared.action);

for (const [id, title, goal] of modules) {
  const featureId = `feature.${id}`;
  const isSpecial = ['retrieve-clustering', 'retrieve-context', 'retrieve-realtime'].includes(id);
  write('features', id, {
    id: featureId,
    version: '0.1.0',
    title,
    status: 'approved',
    goal,
    inputs: [
      { name: 'name', type: 'string', required: !isSpecial },
      { name: 'filterQuery', type: 'string', required: false },
    ],
    rules: isSpecial
      ? ['不改 Vue2 / v1 代码', '状态所有权在 Vue3 controller']
      : ['名称去空白', '同列表名称不可重复', '状态过滤与关键字过滤可叠加'],
    dependencies: isSpecial
      ? [
          'data.log-record',
          `state.${id}`,
          `ui.${id}`,
          id === 'retrieve-clustering' ? 'action.group-clusters' : id === 'retrieve-context' ? 'action.open-context' : 'action.append-realtime',
        ]
      : ['data.resource-item', 'state.resource-list', 'ui.resource-list', 'action.mutate-resource'],
    acceptance: isSpecial
      ? [
          { id: 'AC-001', given: '存在业务数据', when: '执行该模块主操作', then: '按契约更新状态' },
          { id: 'AC-002', given: '存在过滤或并发条件', when: '再次操作', then: '结果只反映当前条件' },
        ]
      : [
          { id: 'AC-001', given: '列表中有多条资源', when: '提交过滤关键字', then: '只展示名称或关键字匹配项' },
          { id: 'AC-002', given: '资源状态不同', when: '按状态过滤', then: '只保留该状态' },
          { id: 'AC-003', given: '已存在同名资源', when: '再次保存该名称', then: '进入 error 且不新增' },
          { id: 'AC-004', given: '目标资源存在', when: '删除', then: '列表不再包含该项' },
        ],
  });
  if (specialContracts[id]) {
    write('state', id, specialContracts[id].state);
    write('ui', id, specialContracts[id].ui);
    write('actions', specialContracts[id].action.id.replace('action.', ''), specialContracts[id].action);
  }
  if (!isSpecial) {
    write('test-cases', id, {
      id: `test.${id}`,
      feature: featureId,
      scenarios: [
        { id: 'TC-001', acceptance: 'AC-001', command: 'node --test --experimental-strip-types src/shared/resource/resource-list-controller.test.mjs', expect: 'filter' },
        { id: 'TC-002', acceptance: 'AC-002', command: 'node --test --experimental-strip-types src/shared/resource/resource-list-controller.test.mjs', expect: 'status' },
        { id: 'TC-003', acceptance: 'AC-003', command: 'node --test --experimental-strip-types src/shared/resource/resource-list-controller.test.mjs', expect: 'duplicate' },
        { id: 'TC-004', acceptance: 'AC-004', command: 'node --test --experimental-strip-types src/shared/resource/resource-list-controller.test.mjs', expect: 'remove' },
      ],
    });
  }
}

write('test-cases', 'retrieve-clustering', {
  id: 'test.retrieve-clustering',
  feature: 'feature.retrieve-clustering',
  scenarios: [
    { id: 'TC-001', acceptance: 'AC-001', command: 'node --test --experimental-strip-types src/features/retrieve/clustering-controller.test.mjs', expect: 'group' },
    { id: 'TC-002', acceptance: 'AC-002', command: 'node --test --experimental-strip-types src/features/retrieve/clustering-controller.test.mjs', expect: 'filter' },
  ],
});
write('test-cases', 'retrieve-context', {
  id: 'test.retrieve-context',
  feature: 'feature.retrieve-context',
  scenarios: [
    { id: 'TC-001', acceptance: 'AC-001', command: 'node --test --experimental-strip-types src/features/retrieve/context-controller.test.mjs', expect: 'wait' },
    { id: 'TC-002', acceptance: 'AC-002', command: 'node --test --experimental-strip-types src/features/retrieve/context-controller.test.mjs', expect: 'neighbors' },
  ],
});
write('test-cases', 'retrieve-realtime', {
  id: 'test.retrieve-realtime',
  feature: 'feature.retrieve-realtime',
  scenarios: [
    { id: 'TC-001', acceptance: 'AC-001', command: 'node --test --experimental-strip-types src/features/retrieve/realtime-controller.test.mjs', expect: 'ignore' },
    { id: 'TC-002', acceptance: 'AC-002', command: 'node --test --experimental-strip-types src/features/retrieve/realtime-controller.test.mjs', expect: 'buffer' },
  ],
});

console.log('contracts written', modules.length);
