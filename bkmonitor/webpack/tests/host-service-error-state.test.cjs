/**
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
 *
 * BlueKing PaaS is licensed under the MIT License.
 */

'use strict';

process.env.TS_NODE_COMPILER_OPTIONS = JSON.stringify({
  esModuleInterop: true,
  module: 'commonjs',
  moduleResolution: 'node',
  target: 'es2019',
});
process.env.TS_NODE_TRANSPILE_ONLY = '1';

require('ts-node/register/transpile-only');

const assert = require('node:assert/strict');
const test = require('node:test');
const Module = require('node:module');

let searchHostInfo;
let searchHostMetric;
let snapshotCreateResponse;
let snapshotPollResponse;
const snapshotCreateRequests = [];
const snapshotPollRequests = [];
const originalLoad = Module._load;
Module._load = function mockHostServiceDependencies(request, parent, isMain) {
  if (request === 'monitor-api/modules/commons') {
    return { getTopoTree: async () => [] };
  }
  if (request === 'monitor-api/modules/performance') {
    return {
      searchHostInfo: (...args) => searchHostInfo(...args),
      searchHostMetric: (...args) => searchHostMetric(...args),
    };
  }
  if (request === 'monitor-api/base') {
    return {
      request: (method, url) => {
        if (method.toLowerCase() === 'post') {
          return async (params, config) => {
            snapshotCreateRequests.push({ config, method, params, url });
            return snapshotCreateResponse;
          };
        }
        return async (id, params, config) => {
          snapshotPollRequests.push({ config, id, method, params, url });
          return snapshotPollResponse;
        };
      },
    };
  }
  return originalLoad.call(this, request, parent, isMain);
};
const {
  getHostInfoList,
  getHostMetricInfoList,
  hostMetricSnapshotService,
} = require('../src/trace/pages/host/services/host-service.ts');
Module._load = originalLoad;

global.window = global.window || {};
global.window.cc_biz_id = 7;

test('host service propagates a base-list request failure', async () => {
  const error = new Error('base request failed');
  searchHostInfo = async () => {
    throw error;
  };

  await assert.rejects(getHostInfoList({}), error);
});

test('host service propagates a metric request failure', async () => {
  const error = new Error('metric request failed');
  searchHostMetric = async () => {
    throw error;
  };

  await assert.rejects(getHostMetricInfoList({ bk_host_ids: [101], end_time: 2, start_time: 1 }), error);
});

test('snapshot adapter maps create manifest and sends an explicit scoped synchronous request', async () => {
  snapshotCreateRequests.length = 0;
  snapshotCreateResponse = {
    canonical_end_time: 190,
    canonical_start_time: 90,
    data: { performance_data: { 101: { cpu_usage: 1 } } },
    expired: false,
    failed_sections: [],
    host_count: 2,
    host_ids_hash: 'hash-1',
    retry_after: 2,
    revision: 3,
    sections: {},
    snapshot_id: 'snapshot-1',
    state: 'RUNNING',
  };

  const result = await hostMetricSnapshotService.create({
    bkBizId: 7,
    bkInstId: 42,
    bkObjId: 'module',
    endTime: 200,
    startTime: 100,
  });

  assert.deepEqual(snapshotCreateRequests, [
    {
      config: { isAsync: false, needMessage: false },
      method: 'post',
      params: {
        bk_biz_id: 7,
        bk_inst_id: 42,
        bk_obj_id: 'module',
        end_time: 200,
        start_time: 100,
      },
      url: 'rest/v2/performance/host_metric_snapshot/',
    },
  ]);
  assert.deepEqual(result, {
    canonicalEndTime: 190,
    canonicalStartTime: 90,
    expired: false,
    failedSections: [],
    hostCount: 2,
    hostIdsHash: 'hash-1',
    retryAfterMs: 2000,
    revision: 3,
    sections: [],
    snapshotId: 'snapshot-1',
    status: 'RUNNING',
  });
});

test('snapshot adapter poll repeats business scope and canonical time and maps completed sections', async () => {
  snapshotPollRequests.length = 0;
  snapshotPollResponse = {
    canonical_end_time: 190,
    canonical_start_time: 90,
    data: {
      agent_status: { 101: { status: 0 } },
      performance_data: { 101: { cpu_usage: 12 } },
    },
    expired: false,
    failed_sections: [],
    host_count: 1,
    host_ids_hash: 'hash-2',
    retry_after: 0.5,
    revision: 5,
    sections: { agent_status: 'READY', performance_data: 'READY' },
    snapshot_id: 'snapshot-1',
    state: 'RUNNING',
  };

  const result = await hostMetricSnapshotService.poll({
    bkBizId: 7,
    bkHostId: 101,
    endTime: 190,
    sinceRevision: 3,
    snapshotId: 'snapshot-1',
    startTime: 90,
  });

  assert.deepEqual(snapshotPollRequests, [
    {
      config: { isAsync: false, needMessage: false },
      id: 'snapshot-1',
      method: 'get',
      params: {
        bk_biz_id: 7,
        bk_host_id: 101,
        end_time: 190,
        since_revision: 3,
        start_time: 90,
      },
      url: 'rest/v2/performance/host_metric_snapshot/{pk}/',
    },
  ]);
  assert.equal(result.retryAfterMs, 500);
  assert.deepEqual(result.sections, [
    { data: { 101: { status: 0 } }, name: 'agent_status' },
    { data: { 101: { cpu_usage: 12 } }, name: 'performance_data' },
  ]);
});

test('snapshot adapter preserves UNAVAILABLE and EXPIRED as terminal domain states', async () => {
  snapshotCreateResponse = {
    data: {},
    expired: false,
    failed_sections: [],
    host_count: 0,
    host_ids_hash: '',
    retry_after: 10,
    revision: 0,
    sections: {},
    state: 'UNAVAILABLE',
  };
  const unavailable = await hostMetricSnapshotService.create({ bkBizId: 7, endTime: 200, startTime: 100 });
  assert.equal(unavailable.snapshotId, undefined);
  assert.equal(unavailable.status, 'UNAVAILABLE');
  assert.equal(unavailable.canonicalStartTime, 100);
  assert.equal(unavailable.canonicalEndTime, 200);

  snapshotPollResponse = { ...snapshotCreateResponse, expired: true, snapshot_id: 'snapshot-1', state: 'EXPIRED' };
  const expired = await hostMetricSnapshotService.poll({
    bkBizId: 7,
    endTime: 190,
    sinceRevision: 0,
    snapshotId: 'snapshot-1',
    startTime: 90,
  });
  assert.equal(expired.status, 'EXPIRED');
  assert.equal(expired.expired, true);
});

test('host id hash uses canonical numeric ordering, deduplication, and SHA-256', async () => {
  assert.equal(
    await hostMetricSnapshotService.hashHostIds([2, 10, 2]),
    '3b5140aab9f8b8240b81687ea6a802d4bb00fc5da32c97b4b2bff91263b3a545'
  );
  assert.equal(
    await hostMetricSnapshotService.hashHostIds([]),
    'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'
  );
});
