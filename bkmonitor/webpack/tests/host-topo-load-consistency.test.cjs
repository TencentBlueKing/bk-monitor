const assert = require('node:assert/strict');
const fs = require('node:fs');
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

global.window = { cc_biz_id: 2 };

const deferred = () => {
  let reject;
  let resolve;
  const promise = new Promise((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, reject, resolve };
};

const loadHostService = getTopoTree => {
  const originalLoad = Module._load;

  Module._load = function loadWithHostServiceStubs(request, parent, isMain) {
    if (request === 'monitor-api/modules/commons') {
      return { getTopoTree };
    }
    if (request === 'monitor-api/modules/performance') {
      return { searchHostInfo: () => [], searchHostMetric: () => ({}) };
    }
    return originalLoad(request, parent, isMain);
  };

  try {
    const modulePath = require.resolve('../src/trace/pages/host/services/host-service.ts');
    delete require.cache[modulePath];
    return require(modulePath);
  } finally {
    Module._load = originalLoad;
  }
};

const createHostTopoContext = ({ getHostTopoTreeByBizId, init }) => {
  const originalLoad = Module._load;

  Module._load = function loadWithHostTopoStubs(request, parent, isMain) {
    if (request === 'vue') {
      return {
        computed: getter => ({
          get value() {
            return getter();
          },
        }),
        onMounted: () => {},
        shallowRef: value => ({ value }),
        watch: () => {},
      };
    }
    if (request === '@vueuse/core') {
      return { useDebounceFn: fn => fn };
    }
    if (request === 'vue-router') {
      return { useRoute: () => ({ query: {} }) };
    }
    if (request === '../services/host-service') {
      return { getHostTopoTreeByBizId };
    }
    if (request === '../utils/host-list-core') {
      return { handleCreateCompares: value => value, handleCreateItemId: value => value.id };
    }
    if (request === '../utils/topo-tree') {
      return { isHostNode: () => false };
    }
    if (request === './use-host-topo-tree-worker') {
      return {
        useHostTopoTreeWorker: () => ({
          collapseAll: async () => ({ rows: [], total: 0 }),
          expandAll: async () => ({ rows: [], total: 0 }),
          getRange: async () => ({ rows: [], total: 1 }),
          init,
          setFilter: async () => ({ rows: [], total: 0 }),
          toggle: async () => ({ rows: [], total: 0 }),
        }),
      };
    }
    if (request === '@/store/modules/host') {
      return {
        useHostStore: () => ({
          metricAggregationState: { compareTargets: [], compareType: 'none' },
        }),
      };
    }
    return originalLoad(request, parent, isMain);
  };

  try {
    const modulePath = require.resolve('../src/trace/pages/host/composables/use-host-topo-tree.ts');
    delete require.cache[modulePath];
    const { useHostTopoTree } = require(modulePath);
    return useHostTopoTree({ value: '' });
  } finally {
    Module._load = originalLoad;
  }
};

const createInitResult = treeData => ({
  selectedNode: treeData[0],
  selectedNodeOffset: -1,
  total: treeData.length,
});

test('连续加载拓扑时旧网络响应不得覆盖后返回的新状态', async () => {
  const firstRequest = deferred();
  const secondRequest = deferred();
  const requests = [firstRequest, secondRequest];
  const context = createHostTopoContext({
    getHostTopoTreeByBizId: () => requests.shift().promise,
    init: async treeData => createInitResult(treeData),
  });
  const firstLoad = context.loadTopoTree();
  const secondLoad = context.loadTopoTree();
  const newerTree = [{ children: [], id: 'newer' }];
  const olderTree = [{ children: [], id: 'older' }];

  secondRequest.resolve(newerTree);
  await secondLoad;
  firstRequest.resolve(olderTree);
  await firstLoad;

  assert.equal(context.selectedNode.value.id, 'newer');
});

test('新请求完成后旧 Worker 初始化结果不得覆盖新状态', async () => {
  const firstRequest = deferred();
  const secondRequest = deferred();
  const firstInit = deferred();
  const firstInitStarted = deferred();
  const requests = [firstRequest, secondRequest];
  const context = createHostTopoContext({
    getHostTopoTreeByBizId: () => requests.shift().promise,
    init: treeData => {
      if (treeData[0].id === 'older') {
        firstInitStarted.resolve();
        return firstInit.promise;
      }
      return Promise.resolve(createInitResult(treeData));
    },
  });
  const olderTree = [{ children: [], id: 'older' }];
  const newerTree = [{ children: [], id: 'newer' }];
  const firstLoad = context.loadTopoTree();

  firstRequest.resolve(olderTree);
  await firstInitStarted.promise;
  const secondLoad = context.loadTopoTree();
  secondRequest.resolve(newerTree);
  await secondLoad;
  firstInit.resolve(createInitResult(olderTree));
  await firstLoad;

  assert.equal(context.selectedNode.value.id, 'newer');
});

test('拓扑服务请求失败时必须向页面层传播异常', async () => {
  const requestError = new Error('topology request failed');
  const { getHostTopoTreeByBizId } = loadHostService(() => Promise.reject(requestError));

  await assert.rejects(() => getHostTopoTreeByBizId(), requestError);
});

test('最新拓扑请求失败时展示错误态且重试成功后恢复', async () => {
  const firstRequest = deferred();
  const secondRequest = deferred();
  const requests = [firstRequest, secondRequest];
  const context = createHostTopoContext({
    getHostTopoTreeByBizId: () => requests.shift().promise,
    init: async treeData => createInitResult(treeData),
  });
  const firstLoad = context.loadTopoTree();

  firstRequest.reject(new Error('topology request failed'));
  await firstLoad;
  assert.equal(context.loadError.value, true);
  assert.equal(context.loading.value, false);

  const secondLoad = context.loadTopoTree();
  secondRequest.resolve([{ children: [], id: 'recovered' }]);
  await secondLoad;
  assert.equal(context.loadError.value, false);
  assert.equal(context.selectedNode.value.id, 'recovered');
});

test('旧拓扑请求失败不得覆盖后发成功状态', async () => {
  const firstRequest = deferred();
  const secondRequest = deferred();
  const requests = [firstRequest, secondRequest];
  const context = createHostTopoContext({
    getHostTopoTreeByBizId: () => requests.shift().promise,
    init: async treeData => createInitResult(treeData),
  });
  const firstLoad = context.loadTopoTree();
  const secondLoad = context.loadTopoTree();

  secondRequest.resolve([{ children: [], id: 'newer' }]);
  await secondLoad;
  firstRequest.reject(new Error('stale topology request failed'));
  await firstLoad;

  assert.equal(context.loadError.value, false);
  assert.equal(context.selectedNode.value.id, 'newer');
});

test('拓扑错误态提供 500 提示和刷新操作', () => {
  const source = fs.readFileSync(
    path.resolve(__dirname, '../src/trace/pages/host/components/host-topo-tree/host-topo-tree.tsx'),
    'utf8'
  );

  assert.match(source, /ctx\.loadError\.value[\s\S]*<EmptyStatus[\s\S]*type='500'/);
  assert.match(source, /<EmptyStatus[\s\S]*onOperation=\{ctx\.handleRefresh\}/);
});
