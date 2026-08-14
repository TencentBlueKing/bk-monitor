/**
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent. All rights reserved.
 *
 * BlueKing PaaS is licensed under the MIT License.
 */

'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const createHost = (bkHostId, ip) => ({
  bk_cloud_id: 0,
  bk_host_id: bkHostId,
  bk_host_innerip: ip,
  module: [],
});

const createWorkerHarness = () => {
  const source = fs.readFileSync(
    path.resolve(__dirname, '../src/trace/pages/host/workers/host-list.worker.raw.js'),
    'utf8'
  );
  const messages = [];
  const workerSelf = { postMessage: message => messages.push(message) };
  vm.runInNewContext(source, { Map, Number, Object, Set, String, self: workerSelf });
  let requestId = 0;
  return {
    send(message) {
      messages.length = 0;
      requestId += 1;
      workerSelf.onmessage({ data: { ...message, requestId } });
      assert.equal(messages.length, 1);
      return messages[0];
    },
  };
};

const defaultComputeParams = {
  activeCategory: '',
  keyword: '',
  page: 1,
  pageSize: 50,
  selectedNode: null,
  sortInfo: '',
  stickyValue: {},
  where: [],
};

test('page metrics overlay the visible page without changing global sort or statistics', () => {
  const worker = createWorkerHarness();
  worker.send({
    baseList: [createHost(101, '10.0.0.1'), createHost(102, '10.0.0.2')],
    epoch: 1,
    type: 'INIT_BASE',
  });
  worker.send({
    epoch: 1,
    metricListMap: { 102: { alarm_count: [], component: [], cpu_usage: 99 } },
    type: 'PATCH_METRICS',
  });

  const firstPage = worker.send({
    params: { ...defaultComputeParams, pageSize: 1, sortInfo: '-cpu_usage' },
    type: 'COMPUTE',
  });
  assert.equal(firstPage.pagedRows[0].bk_host_id, 101);
  assert.equal(firstPage.categoryStats.cpu, 0);

  const secondPage = worker.send({
    params: { ...defaultComputeParams, page: 2, pageSize: 1 },
    type: 'COMPUTE',
  });
  assert.equal(secondPage.pagedRows[0].bk_host_id, 102);
  assert.equal(secondPage.pagedRows[0].cpu_usage, 99);
});

test('running snapshot keeps base keyword search including IPv6 but excludes page-only process fields', () => {
  const worker = createWorkerHarness();
  worker.send({
    baseList: [
      {
        ...createHost(101, '10.0.0.1'),
        bk_host_innerip_v6: '2001:db8::1',
        bk_host_name: 'base-host',
      },
    ],
    epoch: 4,
    type: 'INIT_BASE',
  });
  const pageMetric = {
    101: {
      component: [{ display_name: 'redis', status: 0 }],
    },
  };
  worker.send({ epoch: 4, metricListMap: pageMetric, type: 'PATCH_METRICS' });

  const baseMatch = worker.send({
    params: { ...defaultComputeParams, keyword: 'base-host' },
    type: 'COMPUTE',
  });
  const processMatch = worker.send({
    params: { ...defaultComputeParams, keyword: 'redis' },
    type: 'COMPUTE',
  });
  const ipv6Match = worker.send({
    params: { ...defaultComputeParams, keyword: '2001:db8' },
    type: 'COMPUTE',
  });
  assert.equal(baseMatch.total, 1);
  assert.equal(processMatch.total, 0);
  assert.equal(ipv6Match.total, 1);

  worker.send({ epoch: 4, metricListMap: pageMetric, type: 'REPLACE_METRICS' });
  const readyProcessMatch = worker.send({
    params: { ...defaultComputeParams, keyword: 'redis' },
    type: 'COMPUTE',
  });
  const readyIpv6Match = worker.send({
    params: { ...defaultComputeParams, keyword: '2001:db8' },
    type: 'COMPUTE',
  });
  assert.equal(readyProcessMatch.total, 1);
  assert.equal(readyIpv6Match.total, 1);
});

test('snapshot replacement atomically enables global metric semantics and clears page overlays', () => {
  const worker = createWorkerHarness();
  worker.send({
    baseList: [createHost(101, '10.0.0.1'), createHost(102, '10.0.0.2')],
    epoch: 7,
    type: 'INIT_BASE',
  });
  worker.send({ epoch: 7, metricListMap: { 101: { cpu_usage: 99 } }, type: 'PATCH_METRICS' });
  worker.send({
    epoch: 7,
    metricListMap: {
      101: { alarm_count: [], component: [], cpu_usage: 1 },
      102: { alarm_count: [], component: [], cpu_usage: 88 },
    },
    type: 'REPLACE_METRICS',
  });

  const result = worker.send({
    params: { ...defaultComputeParams, pageSize: 1, sortInfo: '-cpu_usage' },
    type: 'COMPUTE',
  });
  assert.equal(result.pagedRows[0].bk_host_id, 102);
  assert.equal(result.pagedRows[0].cpu_usage, 88);
  assert.equal(result.categoryStats.cpu, 1);

  const host101 = worker.send({
    params: { ...defaultComputeParams, pageSize: 1 },
    type: 'COMPUTE',
  });
  assert.equal(host101.pagedRows[0].cpu_usage, 1);
});

test('worker rejects page and snapshot results from an obsolete dataset epoch', () => {
  const worker = createWorkerHarness();
  worker.send({ baseList: [createHost(202, '10.0.0.2')], epoch: 2, type: 'INIT_BASE' });

  const pageResult = worker.send({ epoch: 1, metricListMap: { 202: { cpu_usage: 99 } }, type: 'PATCH_METRICS' });
  const snapshotResult = worker.send({
    epoch: 1,
    metricListMap: { 202: { cpu_usage: 88 } },
    type: 'REPLACE_METRICS',
  });
  const result = worker.send({ params: defaultComputeParams, type: 'COMPUTE' });

  assert.equal(pageResult.applied, false);
  assert.equal(snapshotResult.applied, false);
  assert.equal(result.pagedRows[0].cpu_usage, undefined);
});

test('reset metrics clears both committed snapshot data and page overlays', () => {
  const worker = createWorkerHarness();
  worker.send({ baseList: [createHost(101, '10.0.0.1')], epoch: 3, type: 'INIT_BASE' });
  worker.send({ epoch: 3, metricListMap: { 101: { cpu_usage: 99 } }, type: 'PATCH_METRICS' });
  worker.send({ epoch: 3, type: 'RESET_METRICS' });

  const result = worker.send({ params: defaultComputeParams, type: 'COMPUTE' });
  assert.equal(result.pagedRows[0].cpu_usage, undefined);
  assert.equal(result.categoryStats.cpu, 0);
});
