const assert = require('node:assert/strict');
const Module = require('node:module');
const path = require('node:path');
const test = require('node:test');

process.env.TS_NODE_PROJECT = path.resolve(__dirname, '../src/trace/tsconfig.json');
process.env.TS_NODE_COMPILER_OPTIONS = JSON.stringify({
  esModuleInterop: true,
  module: 'commonjs',
  moduleResolution: 'node',
});
require('ts-node/register/transpile-only');

const graphServicePath = path.resolve(__dirname, '../src/trace/pages/host/services/graph-service.ts');

const loadGraphService = performanceApi => {
  const originalLoad = Module._load;
  Module._load = function (request, parent, isMain) {
    if (request === 'monitor-api/modules/performance') {
      return performanceApi;
    }
    return originalLoad.call(this, request, parent, isMain);
  };

  delete require.cache[require.resolve(graphServicePath)];
  try {
    return require(graphServicePath);
  } finally {
    Module._load = originalLoad;
  }
};

const createPerformanceApi = overrides => ({
  getHostMetricGroupPanelOrder: async () => [],
  getHostViewsPanels: async () => [],
  getProcessMetricGroupPanelOrder: async () => [],
  getProcessViewsPanels: async () => [],
  ...overrides,
});

test('进程面板首次请求失败后不会缓存空结果，下一次打开详情可重试恢复', async () => {
  const panels = [{ id: 'system', panels: [], title: '系统' }];
  let requestCount = 0;
  const service = loadGraphService(
    createPerformanceApi({
      getProcessViewsPanels: async () => {
        requestCount += 1;
        if (requestCount === 1) {
          throw new Error('temporary failure');
        }
        return panels;
      },
    })
  );

  assert.deepEqual(await service.getProcessViewsPanelsApi(), []);
  assert.deepEqual(await service.getProcessViewsPanelsApi(), panels);
  assert.equal(requestCount, 2);
});

test('进程面板成功返回的真实空配置仍会缓存', async () => {
  let requestCount = 0;
  const service = loadGraphService(
    createPerformanceApi({
      getProcessViewsPanels: async () => {
        requestCount += 1;
        return [];
      },
    })
  );

  assert.deepEqual(await service.getProcessViewsPanelsApi(), []);
  assert.deepEqual(await service.getProcessViewsPanelsApi(), []);
  assert.equal(requestCount, 1);
});

test('进程面板排序首次请求失败后不会缓存空结果，下一次打开详情可重试恢复', async () => {
  const order = [{ id: 'system', panels: [], title: '系统' }];
  let requestCount = 0;
  const service = loadGraphService(
    createPerformanceApi({
      getProcessMetricGroupPanelOrder: async () => {
        requestCount += 1;
        if (requestCount === 1) {
          throw new Error('temporary failure');
        }
        return order;
      },
    })
  );

  assert.deepEqual(await service.getProcessMetricGroupPanelOrderApi(), []);
  assert.deepEqual(await service.getProcessMetricGroupPanelOrderApi(), order);
  assert.equal(requestCount, 2);
});
