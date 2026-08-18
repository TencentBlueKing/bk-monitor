const assert = require('node:assert/strict');
const fs = require('node:fs');
const { createRequire } = require('node:module');
const path = require('node:path');
const test = require('node:test');
const ts = require('typescript');

global.window = {
  enable_cmdb_level: true,
  i18n: {
    t: value => value,
  },
  open() {},
};
global.location = { hash: '#/trace/host', href: 'https://bkmonitor.example.com/#/trace/host' };

const readSource = relativePath => fs.readFileSync(path.resolve(__dirname, relativePath), 'utf8');
const loadTsModule = (relativePath, requireModule = require) => {
  const source = readSource(relativePath);
  const code = ts.transpileModule(source, {
    compilerOptions: {
      esModuleInterop: true,
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
global.h = vue.h;

const useTestHostStore = pinia.defineStore('host-tabs-keyboard-accessibility-test', {
  state: () => ({ activeTab: '' }),
});

let currentRoute;
let currentRouter;
let currentStore;
const hostContentTabs = loadTsModule(
  '../src/trace/pages/host/components/host-content-tabs/host-content-tabs.tsx',
  id => {
    if (id === 'vue') return vue;
    if (id === 'pinia') return pinia;
    if (id === 'vue-i18n') return { useI18n: () => ({ t: value => value }) };
    if (id === 'vue-router') return { useRoute: () => currentRoute, useRouter: () => currentRouter };
    if (id === '../../constants/constants') return constants;
    if (id === '../../utils/topo-tree') return topoTree;
    if (id === '../../../../store/modules/host') return { useHostStore: () => currentStore };
    return {};
  }
).default;

const setupHostContentTabs = activeTab => {
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
  const props = vue.reactive({ compareHostList: [], readonly: false, selectedNode: { bk_host_id: 5 } });
  const scope = vue.effectScope();
  let render;
  scope.run(() => {
    vue.watch(
      () => currentStore.activeTab,
      value => currentRouter.replace({ query: { ...currentRoute.query, activeTab: value } })
    );
    render = hostContentTabs.setup(props, { emit() {} });
  });
  return { appPinia, render, replacements, scope, store: currentStore };
};

const renderTabs = render => {
  const root = render();
  const tabList = root.children[0];
  return { panel: root.children[1], tabList, tabs: tabList.children };
};

test('主机内容页签提供可聚焦的 ARIA tab 语义', () => {
  const harness = setupHostContentTabs('system');
  const { panel, tabList, tabs } = renderTabs(harness.render);

  assert.equal(tabList.props.role, 'tablist');
  assert.equal(tabs[0].type, 'button');
  assert.equal(tabs[0].props.type, 'button');
  assert.equal(tabs[0].props.role, 'tab');
  assert.equal(tabs[0].props['aria-selected'], true);
  assert.equal(tabs[0].props.tabindex, 0);
  assert.equal(tabs[1].props['aria-selected'], false);
  assert.equal(tabs[1].props.tabindex, -1);
  assert.equal(panel.props.role, 'tabpanel');
  assert.equal(tabs[0].props['aria-controls'], panel.props.id);
  assert.equal(tabs[1].props['aria-controls'], panel.props.id);
  assert.equal(panel.props['aria-labelledby'], tabs[0].props.id);

  harness.scope.stop();
  pinia.disposePinia(harness.appPinia);
});

test('主机内容页签支持方向键与首尾键切换并同步深链状态', async () => {
  for (const scenario of [
    { activeTab: 'system', expected: 'process', key: 'ArrowRight', sourceIndex: 0 },
    { activeTab: 'system', expected: 'process', key: 'ArrowLeft', sourceIndex: 0 },
    { activeTab: 'process', expected: 'system', key: 'Home', sourceIndex: 1 },
    { activeTab: 'system', expected: 'process', key: 'End', sourceIndex: 0 },
  ]) {
    const harness = setupHostContentTabs(scenario.activeTab);
    await vue.nextTick();
    const { tabs } = renderTabs(harness.render);
    const focused = [];
    const tabElements = [{ focus: () => focused.push('system') }, { focus: () => focused.push('process') }];
    let prevented = false;

    assert.equal(typeof tabs[scenario.sourceIndex].props.onKeydown, 'function');
    tabs[scenario.sourceIndex].props.onKeydown({
      currentTarget: { parentElement: { querySelectorAll: () => tabElements } },
      key: scenario.key,
      preventDefault: () => {
        prevented = true;
      },
    });
    await vue.nextTick();

    assert.equal(prevented, true, scenario.key);
    assert.equal(harness.store.activeTab, scenario.expected, scenario.key);
    assert.equal(currentRoute.query.activeTab, scenario.expected, scenario.key);
    assert.equal(harness.replacements.at(-1), scenario.expected, scenario.key);
    assert.deepEqual(focused, [scenario.expected], scenario.key);

    harness.scope.stop();
    pinia.disposePinia(harness.appPinia);
  }
});
