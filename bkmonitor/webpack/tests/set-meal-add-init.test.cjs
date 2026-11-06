const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const ts = require('typescript');

const filename = path.join(__dirname, '../src/fta-solutions/pages/setting/set-meal/set-meal-add/set-meal-add.tsx');

function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

const tick = () => new Promise(resolve => setImmediate(resolve));

function createVm(state) {
  const metadata = {
    mealInfo: {
      id: 9,
      name: '套餐A',
      desc: 'desc',
      isEnabled: true,
      strategyCount: 0,
      pluginId: 9,
      pluginType: 'notice',
      executeConfig: {},
    },
  };
  const StoreModule = {
    getNoticeWay: () => state.notice.promise,
    getDimensionList: () => state.dimension.promise,
    getConvergeFunctionList: () => state.converge.promise,
    getVariableDataList: () => state.variables.promise,
    getMealTypeList: () => state.plugins.promise,
    retrieveActionConfig: () => state.retrieve.promise,
  };
  const code = ts.transpileModule(fs.readFileSync(filename, 'utf8'), {
    fileName: filename,
    reportDiagnostics: true,
    compilerOptions: {
      module: ts.ModuleKind.CommonJS,
      target: ts.ScriptTarget.ES2020,
      experimentalDecorators: true,
      jsx: ts.JsxEmit.React,
      jsxFactory: 'h',
    },
  });
  assert.deepEqual(code.diagnostics, []);
  const load = id => {
    if (id === 'vue-property-decorator') {
      const Component = () => target => target;
      Component.registerHooks = () => {};
      const Ref = () => () => {};
      return { Component, Ref };
    }
    if (id === 'vue-tsx-support') {
      class Base {
        constructor(options = {}) {
          Object.assign(this, options);
        }
      }
      return { Component: Base };
    }
    if (id.endsWith('/store/modules/set-meal-add')) return { __esModule: true, default: StoreModule };
    if (id.endsWith('/meal-content/meal-content-data')) {
      return {
        mealDataInit: () => ({ id: 0, pluginType: '' }),
        mealContentDataBackfill: () => ({ id: 9, pluginType: 'notice', notice: {} }),
        transformMealContentParams: () => ({}),
      };
    }
    if (id.endsWith('/meal-basic-info/meal-basic-info')) {
      return { __esModule: true, default: class {} };
    }
    if (id.endsWith('/meal-content/meal-content')) {
      return { __esModule: true, default: class {} };
    }
    if (id.endsWith('/meal-desc/meal-desc')) {
      return { __esModule: true, default: class {} };
    }
    if (id.endsWith('.scss')) return {};
    if (id === 'monitor-common/utils/utils') {
      return {
        deepClone: value => value,
        random: () => 'refresh-key',
        transformDataKey: value => value,
      };
    }
    if (id === 'monitor-pc/store/modules/app') return { SET_NAV_ROUTE_LIST: 'SET_NAV_ROUTE_LIST' };
    return require(id);
  };
  const module = { exports: {} };
  new Function('require', 'module', 'exports', 'window', code.outputText)(load, module, module.exports, {
    i18n: { t: value => value },
  });
  const vm = new module.exports.default({
    $store: { getters: { bizId: 2 }, commit() {} },
    $route: state.route,
    $tc: value => value,
    $t: value => value,
    $bkInfo() {},
    $nextTick: cb => Promise.resolve().then(cb),
  });
  vm.mealInfo = metadata.mealInfo;
  return vm;
}

function createState(params = {}) {
  return {
    route: { params, query: {}, name: 'set-meal-add' },
    notice: deferred(),
    dimension: deferred(),
    converge: deferred(),
    variables: deferred(),
    plugins: deferred(),
    retrieve: deferred(),
  };
}

/**
 * 记录每次 refreshKey 赋值时刻的遮罩状态。
 * 子组件 MealContentNew 的 refreshKey watcher 与父组件渲染在同一轮 flush 执行，
 * 若赋值时页面仍处于遮罩态，子区尚未就绪，模板列表/表单回填会被跳过。
 */
function trackRefreshKey(vm) {
  const snapshots = [];
  let value = vm.refreshKey;
  Object.defineProperty(vm, 'refreshKey', {
    configurable: true,
    get: () => value,
    set(next) {
      value = next;
      snapshots.push({ detailLoading: vm.detailLoading, isLoading: vm.isLoading });
    },
  });
  return snapshots;
}

test('新建态：initMeal 只等套餐类型，其余元数据仍在后台', async () => {
  const state = createState();
  const vm = createVm(state);
  const initPromise = vm.initMeal();
  await tick();
  assert.equal(vm.typeListLoading, true);
  assert.equal(vm.isLoading, true, '首屏遮罩由类型列表决定');

  state.plugins.resolve([]);
  await initPromise;
  await tick();
  assert.equal(vm.typeListLoading, false);
  assert.equal(vm.isLoading, false, '类型列表返回后应解除遮罩，不等 4 个元数据');
  assert.equal(vm.type, 'add');
  // 元数据请求仍在进行中：initMeal 没有被它们阻塞
  state.notice.resolve([]);
  state.dimension.resolve([]);
  state.converge.resolve([]);
  state.variables.resolve([]);
  vm.$destroy?.();
});

test('编辑态：遮罩覆盖类型列表与详情，两者都完成前保持遮罩', async () => {
  const state = createState({ id: '9' });
  const vm = createVm(state);
  const initPromise = vm.initMeal();
  await tick();
  assert.equal(vm.type, 'edit');
  assert.equal(vm.detailLoading, true);
  assert.equal(vm.isLoading, true);

  state.plugins.resolve([]);
  await initPromise;
  assert.equal(vm.typeListLoading, false);
  assert.equal(vm.isLoading, true, '详情未返回时不应解除遮罩，避免空表单可交互');

  state.retrieve.resolve(vm.mealInfo);
  await tick();
  assert.equal(vm.detailLoading, false);
  assert.equal(vm.isLoading, false);
});

test('编辑态：详情先返回时暂存，类型列表就绪后再回填', async () => {
  const state = createState({ id: '9' });
  const vm = createVm(state);
  const initPromise = vm.initMeal();
  await tick();

  state.retrieve.resolve(vm.mealInfo);
  await tick();
  assert.ok(vm.pendingMealInfo, '详情应暂存，等待套餐类型列表');
  assert.equal(vm.mealData.id, 0, '类型列表未就绪时不应提前回填');
  assert.equal(vm.isLoading, true);

  state.plugins.resolve([]);
  await initPromise;
  await tick();
  assert.equal(vm.typeListLoading, false);
  assert.equal(vm.pendingMealInfo, null);
  assert.equal(vm.mealData.id, 9, '类型列表就绪后应完成回填');
  assert.equal(vm.isLoading, false);
  vm.$destroy?.();
});

test('编辑态：详情晚于类型列表返回时，回填前必须先解除遮罩', async () => {
  const state = createState({ id: '9' });
  const vm = createVm(state);
  const snapshots = trackRefreshKey(vm);
  const initPromise = vm.initMeal();
  await tick();

  state.plugins.resolve([]);
  await initPromise;
  assert.equal(vm.typeListLoading, false);
  assert.equal(vm.isLoading, true, '详情未返回时页面仍被遮罩');

  state.retrieve.resolve(vm.mealInfo);
  await tick();
  assert.equal(vm.mealData.id, 9);
  assert.equal(snapshots.length, 1, '回填应触发一次 refreshKey 更新');
  assert.deepEqual(
    snapshots[0],
    { detailLoading: false, isLoading: false },
    'refreshKey 更新时遮罩必须已解除，否则子区未就绪、模板与表单回填被跳过'
  );
});

test('编辑态：详情先返回走暂存路径时，回填时遮罩同样已解除', async () => {
  const state = createState({ id: '9' });
  const vm = createVm(state);
  const snapshots = trackRefreshKey(vm);
  const initPromise = vm.initMeal();
  await tick();

  state.retrieve.resolve(vm.mealInfo);
  await tick();
  assert.equal(snapshots.length, 0, '类型列表未就绪时不应回填');

  state.plugins.resolve([]);
  await initPromise;
  assert.equal(snapshots.length, 1);
  assert.deepEqual(snapshots[0], { detailLoading: false, isLoading: false });
});

test('编辑态：详情失败时解除遮罩、不回填，且 save 不发请求', async t => {
  const errors = [];
  t.mock.method(console, 'error', (...args) => errors.push(args));
  const state = createState({ id: '9' });
  const vm = createVm(state);
  const initPromise = vm.initMeal();
  await tick();

  state.retrieve.reject(new Error('network'));
  await tick();
  assert.equal(vm.detailLoading, false);
  assert.equal(vm.isLoading, true, '类型列表仍在加载');

  state.plugins.resolve([]);
  await initPromise;
  await tick();
  assert.equal(vm.isLoading, false, '失败态不新增 UI：遮罩解除');
  assert.equal(vm.mealData.id, 0, '未回填时保持初始数据');
  assert.equal(errors.length, 1, '失败原因不应被静默吞掉');

  // 让校验整体通过：若没有内部守卫，这里会真的走到 putActionConfig
  vm.basicInfoRefEl = { validator: () => true };
  vm.mealContentRef = { validator: async () => true };
  let putCalls = 0;
  vm.putActionConfig = () => {
    putCalls += 1;
  };
  await vm.save();
  assert.equal(putCalls, 0, '详情未回显时禁止提交，避免用空表单覆盖线上配置');
});

test('编辑态：详情回显成功后 save 正常提交', async () => {
  const state = createState({ id: '9' });
  const vm = createVm(state);
  const initPromise = vm.initMeal();
  state.plugins.resolve([]);
  state.retrieve.resolve(vm.mealInfo);
  await initPromise;
  await tick();
  assert.equal(vm.mealData.id, 9);

  vm.basicInfoRefEl = { validator: () => true };
  vm.mealContentRef = { validator: async () => true };
  let putCalls = 0;
  vm.putActionConfig = () => {
    putCalls += 1;
  };
  await vm.save();
  assert.equal(putCalls, 1, '回显成功后不应被守卫误拦');
});

test('元数据请求异常时记录错误，不阻塞首屏', async t => {
  const errors = [];
  t.mock.method(console, 'error', (...args) => errors.push(args));
  const state = createState();
  const vm = createVm(state);
  const initPromise = vm.initMeal();
  state.plugins.resolve([]);
  await initPromise;
  assert.equal(vm.isLoading, false);

  state.notice.reject(new Error('meta failed'));
  await tick();
  assert.equal(vm.isLoading, false, '元数据异常不应把页面重新遮住');
  assert.equal(errors.length, 1);
  assert.equal(errors[0][0].message, 'meta failed');
});

test('套餐类型列表异常时记录错误并解除遮罩，不发后续回填', async t => {
  const errors = [];
  t.mock.method(console, 'error', (...args) => errors.push(args));
  const state = createState();
  const vm = createVm(state);
  const initPromise = vm.initMeal();
  state.plugins.reject(new Error('plugins failed'));
  await initPromise;
  await tick();
  assert.equal(vm.typeListLoading, false);
  assert.equal(vm.isLoading, false);
  assert.deepEqual(vm.mealTypeList, []);
  assert.equal(errors.length, 1);
});

test('initMeal 重入保护：加载中重复调用不会再次发起请求', async () => {
  const state = createState();
  let pluginCalls = 0;
  const vm = createVm(state);
  const originalGetMealTypeList = vm.getMealTypeList.bind(vm);
  vm.getMealTypeList = () => {
    pluginCalls += 1;
    return originalGetMealTypeList();
  };
  const initPromise = vm.initMeal();
  await vm.initMeal();
  assert.equal(pluginCalls, 1);
  state.plugins.resolve([]);
  await initPromise;
});
