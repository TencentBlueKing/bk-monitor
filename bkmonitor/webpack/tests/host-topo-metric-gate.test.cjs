const assert = require('node:assert/strict');
const fs = require('node:fs');
const { createRequire } = require('node:module');
const path = require('node:path');
const test = require('node:test');
const ts = require('typescript');

global.window = {
  i18n: {
    t: value => value,
  },
};

const readSource = relativePath => fs.readFileSync(path.resolve(__dirname, relativePath), 'utf8');
const loadTsModule = (relativePath, requireModule = require) => {
  const source = readSource(relativePath);
  const code = ts.transpileModule(source, {
    compilerOptions: {
      jsx: ts.JsxEmit.React,
      jsxFactory: 'h',
      module: ts.ModuleKind.CommonJS,
      target: ts.ScriptTarget.ES2022,
    },
  }).outputText;
  const module = { exports: {} };
  Function('exports', 'module', 'require', code)(module.exports, module, requireModule);
  return module.exports;
};

const constants = loadTsModule('../src/trace/pages/host/constants/constants.ts');
const topoTree = loadTsModule('../src/trace/pages/host/utils/topo-tree.ts');
const pinia = require('pinia');
const requireFromPinia = createRequire(require.resolve('pinia'));
const vue = requireFromPinia('vue');
const useTestHostStore = pinia.defineStore('host-topo-metric-gate-test', {
  state: () => ({ activeTab: '' }),
});

let currentRoute;
let currentRouter;
let currentStore;
const hostContentTabs = loadTsModule(
  '../src/trace/pages/host/components/host-content-tabs/host-content-tabs.tsx',
  id => {
    if (id === 'vue') {
      return vue;
    }
    if (id === 'pinia') {
      return pinia;
    }
    if (id === 'vue-i18n') {
      return { useI18n: () => ({ t: value => value }) };
    }
    if (id === 'vue-router') {
      return { useRoute: () => currentRoute, useRouter: () => currentRouter };
    }
    if (id === '../../constants/constants') {
      return constants;
    }
    if (id === '../../utils/topo-tree') {
      return topoTree;
    }
    if (id === '../../../../store/modules/host') {
      return { useHostStore: () => currentStore };
    }
    return {};
  }
).default;

const setupHostContentTabs = (activeTab, selectedNode, enableCmdbLevel) => {
  window.enable_cmdb_level = enableCmdbLevel;
  const appPinia = pinia.createPinia();
  pinia.setActivePinia(appPinia);
  currentStore = useTestHostStore();
  currentRoute = vue.reactive({ query: { activeTab } });
  const replacements = [];
  currentRouter = {
    replace({ query }) {
      replacements.push(query.activeTab);
      currentRoute.query.activeTab = query.activeTab;
    },
    resolve: value => value,
  };
  const props = vue.reactive({ compareHostList: [], readonly: false, selectedNode });
  const scope = vue.effectScope();
  scope.run(() => {
    // 对应 Host 页 urlParams watcher：store 变化后将 activeTab 回写到 URL。
    vue.watch(
      () => currentStore.activeTab,
      value => currentRouter.replace({ query: { ...currentRoute.query, activeTab: value } })
    );
    hostContentTabs.setup(props, { emit() {} });
  });
  return { appPinia, props, replacements, scope, store: currentStore };
};

test('未启用 CMDB 层级能力时 root、set、module 仅展示主机列表', () => {
  assert.equal(typeof constants.getHostPerspectiveTabList, 'function', '缺少拓扑指标能力门禁');

  for (const node of [
    { bk_inst_id: 2, bk_obj_id: 'biz' },
    { bk_inst_id: 3, bk_obj_id: 'set' },
    { bk_inst_id: 4, bk_obj_id: 'module' },
  ]) {
    const perspective = topoTree.isHostNode(node) ? 'host' : 'topo';
    const tabs = constants.getHostPerspectiveTabList(perspective, false);
    assert.deepEqual(
      tabs.map(tab => tab.value),
      ['list'],
      `${node.bk_obj_id} 节点不应展示指标汇聚`
    );
  }
});

test('未启用 CMDB 层级能力时 activeTab=metric 安全回退主机列表', () => {
  assert.equal(typeof constants.resolveHostContentTab, 'function', '缺少直达 URL 回退逻辑');

  const tabs = constants.getHostPerspectiveTabList('topo', false);
  assert.equal(constants.resolveHostContentTab('metric', tabs), 'list');
});

test('启用 CMDB 层级能力时拓扑指标入口和直达恢复保持可用', () => {
  assert.equal(typeof constants.getHostPerspectiveTabList, 'function', '缺少拓扑指标能力门禁');

  const tabs = constants.getHostPerspectiveTabList('topo', true);
  assert.deepEqual(
    tabs.map(tab => tab.value),
    ['list', 'metric']
  );
  assert.equal(constants.resolveHostContentTab('metric', tabs), 'metric');
});

test('CMDB 层级能力开关不影响单主机 system 和 process', () => {
  assert.equal(typeof constants.getHostPerspectiveTabList, 'function', '缺少拓扑指标能力门禁');

  const perspective = topoTree.isHostNode({ bk_host_id: 5 }) ? 'host' : 'topo';
  for (const enabled of [false, true]) {
    const tabs = constants.getHostPerspectiveTabList(perspective, enabled);
    assert.deepEqual(
      tabs.map(tab => tab.value),
      ['system', 'process']
    );
    assert.equal(constants.resolveHostContentTab('system', tabs), 'system');
    assert.equal(constants.resolveHostContentTab('process', tabs), 'process');
  }
});

test('未启用能力时父组件恢复 metric 后，拓扑节点最终同步回写 store 与 URL 为 list', async () => {
  const harness = setupHostContentTabs('metric', { bk_inst_id: 2, bk_obj_id: 'biz' }, false);
  // 对应 Host.onMounted(getUrlParams)：在子组件 setup 后再次从当前 URL 写入 store。
  harness.store.activeTab = currentRoute.query.activeTab;
  await vue.nextTick();

  assert.equal(harness.store.activeTab, 'list');
  assert.equal(currentRoute.query.activeTab, 'list');
  assert.equal(harness.replacements.at(-1), 'list');
  harness.scope.stop();
  pinia.disposePinia(harness.appPinia);
});

test('拓扑异步加载前保留 process 直达意图，加载为主机后仍保持 process', async () => {
  const harness = setupHostContentTabs('process', null, false);
  assert.equal(harness.store.activeTab, 'process');

  harness.store.activeTab = currentRoute.query.activeTab;
  await vue.nextTick();
  harness.props.selectedNode = { bk_host_id: 5 };
  await vue.nextTick();

  assert.equal(harness.store.activeTab, 'process');
  assert.equal(currentRoute.query.activeTab, 'process');
  harness.scope.stop();
  pinia.disposePinia(harness.appPinia);
});

test('启用能力时父组件恢复拓扑 metric 后保持原 Tab 与 URL', async () => {
  const harness = setupHostContentTabs('metric', { bk_inst_id: 2, bk_obj_id: 'biz' }, true);
  harness.store.activeTab = currentRoute.query.activeTab;
  await vue.nextTick();

  assert.equal(harness.store.activeTab, 'metric');
  assert.equal(currentRoute.query.activeTab, 'metric');
  assert.equal(harness.replacements.at(-1), 'metric');
  harness.scope.stop();
  pinia.disposePinia(harness.appPinia);
});
