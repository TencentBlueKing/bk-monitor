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

const deferred = () => {
  let reject;
  let resolve;
  const promise = new Promise((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, reject, resolve };
};

const loadProcessService = getHostProcessList => {
  const originalLoad = Module._load;

  Module._load = function loadWithProcessServiceStubs(request, parent, isMain) {
    if (request === 'monitor-api/modules/scene_view') {
      return { getHostProcessList };
    }
    return originalLoad(request, parent, isMain);
  };

  try {
    const modulePath = require.resolve('../src/trace/pages/host/services/process-service.ts');
    delete require.cache[modulePath];
    return require(modulePath);
  } finally {
    Module._load = originalLoad;
  }
};

const createProcessListContext = getHostProcessList => {
  const originalLoad = Module._load;
  const timeRangeTimestamp = { value: { end_time: 200, start_time: 100 } };

  Module._load = function loadWithProcessListStubs(request, parent, isMain) {
    if (request === 'vue') {
      return {
        computed: getter => ({
          get value() {
            return getter();
          },
        }),
        onScopeDispose: () => {},
        shallowRef: value => ({ value }),
        watch: () => {},
      };
    }
    if (request === 'pinia') {
      return { storeToRefs: store => store };
    }
    if (request === '../../../store/modules/host') {
      return { useHostStore: () => ({ timeRangeTimestamp }) };
    }
    if (request === '../services/process-service') {
      return { getHostProcessList };
    }
    return originalLoad(request, parent, isMain);
  };

  try {
    const modulePath = require.resolve('../src/trace/pages/host/composables/use-process-list.ts');
    delete require.cache[modulePath];
    const { useProcessList } = require(modulePath);
    const host = {
      value: {
        bk_cloud_id: 0,
        bk_host_id: 1,
        ip: '192.0.2.1',
      },
    };
    return {
      context: useProcessList({ host, keyword: { value: '' } }),
      host,
    };
  } finally {
    Module._load = originalLoad;
  }
};

test('进程列表服务请求失败时必须向页面层传播异常', async () => {
  const requestError = new Error('process list request failed');
  const { getHostProcessList } = loadProcessService(() => Promise.reject(requestError));

  await assert.rejects(() => getHostProcessList({}), requestError);
});

test('最新进程列表请求失败时展示错误态且重试成功后恢复', async () => {
  const firstRequest = deferred();
  const secondRequest = deferred();
  const requests = [firstRequest, secondRequest];
  const { context } = createProcessListContext(() => requests.shift().promise);
  const firstLoad = context.loadData();

  firstRequest.reject(new Error('process list request failed'));
  await firstLoad;
  assert.equal(context.loadError.value, true);
  assert.equal(context.loading.value, false);
  assert.deepEqual(context.displayList.value, []);

  const secondLoad = context.loadData();
  secondRequest.resolve([{ id: 'newer', name: 'redis' }]);
  await secondLoad;
  assert.equal(context.loadError.value, false);
  assert.equal(context.loading.value, false);
  assert.deepEqual(
    context.displayList.value.map(item => item.id),
    ['newer']
  );
});

test('旧进程列表请求失败不得覆盖后发成功状态', async () => {
  const firstRequest = deferred();
  const secondRequest = deferred();
  const requests = [firstRequest, secondRequest];
  const { context, host } = createProcessListContext(() => requests.shift().promise);
  const firstLoad = context.loadData();

  host.value = { bk_cloud_id: 0, bk_host_id: 2, ip: '192.0.2.2' };
  const secondLoad = context.loadData();
  secondRequest.resolve([{ id: 'newer', name: 'redis' }]);
  await secondLoad;
  firstRequest.reject(new Error('stale process list request failed'));
  await firstLoad;

  assert.equal(context.loadError.value, false);
  assert.equal(context.loading.value, false);
  assert.deepEqual(
    context.displayList.value.map(item => item.id),
    ['newer']
  );
});

test('进程列表错误态提供 500 提示和刷新操作', () => {
  const hostProcessSource = fs.readFileSync(
    path.resolve(__dirname, '../src/trace/pages/host/components/host-process/host-process.tsx'),
    'utf8'
  );
  const processTableSource = fs.readFileSync(
    path.resolve(__dirname, '../src/trace/pages/host/components/host-process/process-table.tsx'),
    'utf8'
  );

  assert.match(hostProcessSource, /emptyType=\{this\.loadError \? '500' : this\.keyword \? 'search-empty' : 'empty'\}/);
  assert.match(hostProcessSource, /onRetry=\{this\.loadData\}/);
  assert.match(processTableSource, /this\.emptyType === '500'[\s\S]*<EmptyStatus[\s\S]*type='500'/);
  assert.match(processTableSource, /<EmptyStatus[\s\S]*onOperation=\{\(\) => this\.\$emit\('retry'\)\}/);
});
