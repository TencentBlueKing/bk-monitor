const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const ts = require('typescript');
const Vue = require('vue');
const VueRouter = require('vue-router');
const compiler = require('vue/compiler-sfc');

Vue.use(VueRouter);
const root = path.join(__dirname, '..');
const filename = path.join(root, 'src/monitor-pc/pages/collector-config/collector-config.vue');
const source = fs.readFileSync(process.env.COLLECTOR_CONFIG_TEST_SOURCE || filename, 'utf8');
const descriptor = compiler.parse({ source, filename });
const template = compiler.compileTemplate({ source: descriptor.template.content, filename });
assert.deepEqual(template.errors, []);
const renderOptions = new Function(`${template.code}; return { render, staticRenderFns };`)();

function load(code, dependencies = {}, globals = {}) {
  const compiled = ts.transpileModule(code, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  }).outputText;
  const module = { exports: {} };
  new Function('require', 'module', 'exports', ...Object.keys(globals), compiled)(
    id => dependencies[id] || { default: {} },
    module,
    module.exports,
    ...Object.values(globals)
  );
  return module.exports;
}

const utilsSource = fs.readFileSync(path.join(root, 'src/monitor-common/utils/index.ts'), 'utf8');
const utilsAst = ts.createSourceFile('utils.ts', utilsSource, ts.ScriptTarget.Latest, true);
const routeUtils = utilsAst.statements
  .filter(
    node =>
      ts.isVariableStatement(node) &&
      node.declarationList.declarations.some(declaration =>
        ['parseBizId', 'getBizRouteHref'].includes(declaration.name.getText(utilsAst))
      )
  )
  .map(node => node.getText(utilsAst))
  .join('\n');
const routes = load(fs.readFileSync(path.join(root, 'src/monitor-pc/router/integrated/collector-config.ts'), 'utf8'), {
  '../../common': { applyGuidePage: routes => routes },
}).default;

function setup(bizId = 101) {
  const opened = [];
  const pushed = [];
  const replaced = [];
  const deleted = [];
  const mutations = [];
  const redirected = [];
  const location = {
    origin: 'https://monitor.example.com',
    pathname: '/monitor/',
    replace: href => redirected.push(href),
  };
  const window = { cc_biz_id: bizId, location, open: (...args) => opened.push(args) };
  const utils = load(routeUtils, {}, { location });
  const component = load(
    descriptor.script.content,
    {
      'monitor-common/utils': { ...utils, commonPageSizeGet: () => 10, commonPageSizeSet() {} },
      'monitor-api/modules/collecting': {
        deleteCollectConfig: data => {
          deleted.push(data);
          return Promise.resolve();
        },
      },
      vuex: { createNamespacedHelpers: () => ({ mapMutations: () => ({}) }) },
      '../../mixins/authorityMixin': { default: () => ({}) },
      '../../store/modules/collector-config': {
        SET_ADD_DATA: 'SET_ADD_DATA',
        SET_ADD_MODE: 'SET_ADD_MODE',
        SET_OBJECT_TYPE: 'SET_OBJECT_TYPE',
      },
    },
    { window }
  ).default;
  const router = new VueRouter({
    mode: 'abstract',
    routes,
  });
  const context = {
    bizId,
    $t: value => value,
    $tc: value => value,
    $router: {
      resolve: value => router.resolve(value),
      push: value => pushed.push(value),
      replace: value => replaced.push(value),
    },
    authority: { MANAGE_AUTH: false },
  };
  Object.assign(context, component.data.call(context));
  for (const [name, method] of Object.entries(component.methods)) context[name] = method.bind(context);
  for (const name of ['SET_ADD_DATA', 'SET_ADD_MODE', 'SET_OBJECT_TYPE'])
    context[name] = value => mutations.push([name, value]);
  return { context, component, window, opened, pushed, replaced, deleted, mutations, redirected };
}

function row(bizId = 202) {
  return {
    id: 303,
    bizId,
    name: 'CPU & memory / usage',
    space_name: 'Example business',
    status: 'STARTED',
    taskStatus: 'SUCCESS',
    doingStatus: false,
    needUpdate: true,
    collectType: 'Script',
    objectTypeEn: 'HOST',
    updateParams: { pluginId: 'example_plugin' },
  };
}

for (const method of ['handleShowDetail', 'handleCheckView', 'handleCheckStatus']) {
  test(`${method} opens the owning business without changing the current page`, () => {
    const state = setup();
    state.context[method](row());
    assert.equal(state.pushed.length, 0);
    assert.equal(state.opened.length, 1);
    const [href, target, features] = state.opened[0];
    assert.equal(target, '_blank');
    assert.equal(features, 'noopener');
    const url = new URL(href);
    assert.equal(url.searchParams.get('bizId'), '202');
    assert.match(url.hash, /\/303(?:\?|$)/);
    assert.equal(state.window.cc_biz_id, 101);
    assert.equal(state.context.bizId, 101);
    if (method === 'handleCheckView') {
      const query = new URLSearchParams(url.hash.split('?')[1]);
      assert.equal(query.get('name'), row().name);
      assert.deepEqual(JSON.parse(query.get('customQuery')), { pluginId: 'example_plugin', bizId: 202 });
    }
  });

  test(`${method} retains same-business navigation`, () => {
    const state = setup();
    state.context[method](row(101));
    assert.equal(state.opened.length, 0);
    assert.equal(state.pushed.length, 1);
    assert.equal(state.pushed[0].params.id, 303);
  });
}

test('cross-business write handlers cannot open dialogs, mutate state, navigate, or call deletion', () => {
  const state = setup();
  const data = row();
  state.context.popover.data = data;
  state.context.dialog.update.data = data;
  const snapshot = JSON.stringify({
    popover: state.context.popover,
    dialog: state.context.dialog,
    task: state.context.collectorTaskData,
  });
  state.context.handleOperatorOver(data, {}, 0);
  state.context.handleUpdateTarget(data);
  state.context.handleConfigUpdate(data);
  state.context.handleShowAdd('edit', data);
  state.context.handleShowAdd('edit');
  state.context.handleDeleteRow();
  state.context.handleCloneConfig();
  state.context.handleSubmitDelete();
  state.context.handleOpenOrClose();
  state.context.handleOpenUpgradePage({});
  assert.deepEqual(state.pushed, []);
  assert.deepEqual(state.deleted, []);
  assert.deepEqual(state.mutations, []);
  assert.equal(state.context.delDialogShow, false);
  assert.equal(
    JSON.stringify({
      popover: state.context.popover,
      dialog: state.context.dialog,
      task: state.context.collectorTaskData,
    }),
    snapshot
  );
});

test('same-business upgrade, target editing, clone, and create remain available', () => {
  const state = setup();
  const data = row(101);
  state.context.handleConfigUpdate(data);
  assert.equal(state.context.dialog.update.show, true);
  data.needUpdate = false;
  state.context.handleUpdateTarget(data);
  state.context.popover.data = data;
  state.context.handleCloneConfig();
  state.context.handleShowAdd('add');
  assert.deepEqual(
    state.pushed.map(route => route.name),
    ['collect-config-node', 'collect-config-clone', 'collect-config-add']
  );
});

test('asynchronous list deep link enters the owning business without opening a popup', async () => {
  const state = setup();
  state.context.$route = { query: { id: '303' } };
  state.context.table.data = [row()];
  state.context.showGuidePage = false;
  state.context.fetchCollectConfigStat = () => {};
  state.context.getCollectionConfigList = () => Promise.resolve({});
  state.context.initPageData();
  await new Promise(resolve => setImmediate(resolve));
  assert.deepEqual(state.opened, []);
  assert.equal(new URL(state.redirected[0]).searchParams.get('bizId'), '202');
  assert.match(new URL(state.redirected[0]).hash, /\/303$/);
  assert.deepEqual(state.replaced, [{ name: 'collect-config' }]);
});

function allNodes(nodes) {
  return (Array.isArray(nodes) ? nodes : [nodes])
    .filter(Boolean)
    .flatMap(node => [node, ...allNodes(node.children || [])]);
}

function texts(nodes) {
  return allNodes(nodes)
    .map(node => node.text || '')
    .join('');
}

test('rendered cross-business row is read-only and read links do not require source-business manage permission', () => {
  const state = setup();
  const data = Object.fromEntries(
    Object.entries(state.context).filter(([key]) => !key.startsWith('$') && !(key in state.component.computed))
  );
  const vm = new Vue({
    ...renderOptions,
    beforeCreate() {
      this.$store = { getters: { bizId: 101, bkNodeManHost: 'https://nodes.example.com/' } };
    },
    data: () => ({
      ...data,
      statsLoading: false,
      listLoading: false,
      filterTabList: [{ name: '全部', total: 1, data: { startedNum: 1 } }],
    }),
    methods: { $t: value => value, $tc: value => value },
    computed: {
      ...state.component.computed,
      showGuidePage: () => false,
      selectedColumns() {
        return this.table.columns.filter(column => column.show);
      },
      activeTabItem() {
        return this.filterTabList[0];
      },
      isShowPagination: () => true,
    },
  });
  const vnode = vm._render();
  const columns = allNodes(vnode).filter(node => node.tag === 'bk-table-column' && node.data?.scopedSlots?.default);
  const cells = columns.flatMap(column => column.data.scopedSlots.default({ row: row(), $index: 0 }));
  const content = texts(cells);
  assert.ok(content.includes('查看'));
  assert.ok(content.includes('可视化'));
  for (const text of ['升级', '编辑', '增删目标']) assert.ok(!content.includes(text), text);
  assert.ok(!allNodes(cells).some(node => node.data?.staticClass === 'col-operator-more'));
  const visualization = allNodes(cells).find(node => texts(node).trim().startsWith('可视化') && node.data?.directives);
  assert.equal(visualization.data.directives.find(directive => directive.name === 'authority').value.active, false);
  assert.ok(texts(vnode).includes('本业务'));
  assert.ok(vm.table.columns.find(column => column.prop === 'space_name').show);
  vm.$destroy();
});

test('business scope in links supports negative space IDs', () => {
  const state = setup();
  state.context.handleShowDetail(row(-404));
  assert.equal(new URL(state.opened[0][0]).searchParams.get('bizId'), '-404');
});
