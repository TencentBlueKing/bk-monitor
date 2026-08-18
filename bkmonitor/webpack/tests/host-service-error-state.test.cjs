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
  return originalLoad.call(this, request, parent, isMain);
};
const { getHostInfoList, getHostMetricInfoList } = require('../src/trace/pages/host/services/host-service.ts');
Module._load = originalLoad;

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
