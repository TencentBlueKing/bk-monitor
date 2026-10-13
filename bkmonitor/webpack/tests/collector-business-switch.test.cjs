const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const ts = require('typescript');

// Only the node operations required by Vue's patcher; events and layout are not simulated.
function domNode(tag = '', nodeType = 1, text = '') {
  return {
    nodeType,
    tagName: tag.toUpperCase(),
    textContent: text,
    parentNode: null,
    children: [],
    attributes: {},
    style: {
      setProperty(name, value) {
        this[name] = value;
      },
    },
    get childNodes() {
      return this.children;
    },
    get nextSibling() {
      return this.parentNode?.children[this.parentNode.children.indexOf(this) + 1] || null;
    },
    appendChild(child) {
      return this.insertBefore(child, null);
    },
    insertBefore(child, reference) {
      child.parentNode?.removeChild(child);
      const index = reference ? this.children.indexOf(reference) : this.children.length;
      this.children.splice(index, 0, child);
      child.parentNode = this;
      return child;
    },
    removeChild(child) {
      this.children.splice(this.children.indexOf(child), 1);
      child.parentNode = null;
    },
    setAttribute(name, value) {
      this.attributes[name] = value;
    },
    removeAttribute(name) {
      delete this.attributes[name];
    },
    hasAttribute(name) {
      return name in this.attributes;
    },
    addEventListener() {},
    removeEventListener() {},
  };
}
global.document = {
  createElement: domNode,
  createElementNS: (_, tag) => domNode(tag),
  createTextNode: text => domNode('', 3, text),
  createComment: text => domNode('', 8, text),
  createEvent: () => ({ timeStamp: Date.now() }),
};
global.window = {
  navigator: { userAgent: 'node' },
  document,
  history: {},
  addEventListener() {},
  removeEventListener() {},
  i18n: { t: value => value },
};
global.localStorage = { getItem: () => null };
const Vue = require('vue');
const VueRouter = require('vue-router');
const compiler = require('vue/compiler-sfc');
Vue.use(VueRouter);
Vue.config.productionTip = false;
Vue.config.devtools = false;
Vue.config.ignoredElements = [/^bk-/, 'i18n'];
for (const name of ['bkloading', 'authority', 'en-style', 'bk-tooltips']) Vue.directive(name, {});
Vue.component('bk-table', { render: h => h('div'), methods: { doLayout() {} } });

const root = path.join(__dirname, '..');
const filename = path.join(root, 'src/monitor-pc/pages/collector-config/collector-config.vue');
const source = fs.readFileSync(process.env.COLLECTOR_CONFIG_TEST_SOURCE || filename, 'utf8');
const descriptor = compiler.parse({ source, filename });
const template = compiler.compileTemplate({ source: descriptor.template.content, filename });
assert.deepEqual(template.errors, []);
const renderOptions = new Function(`${template.code}; return { render, staticRenderFns };`)();
const flush = async () => {
  await Vue.nextTick();
  await new Promise(resolve => setImmediate(resolve));
};
const stub = { render: h => h('div') };
const types = [{ id: 'Script', name: 'Script', nums: {} }];
const config = (id = 303, bizId = 101) => ({
  id,
  bk_biz_id: bizId,
  name: `example-${id}`,
  collect_type: 'Script',
  status: 'STARTED',
  task_status: 'SUCCESS',
  target_object_type: 'HOST',
  target_node_type: 'INSTANCE',
  total_instance_count: 1,
  plugin_id: 'example-plugin',
});
const listResponse = rows => ({ data: { config_list: rows, total: rows.length, type_list: types } });

function load(source, dependencies, timers) {
  const code = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  }).outputText;
  const module = { exports: {} };
  new Function('require', 'module', 'exports', 'setTimeout', 'clearTimeout', code)(
    id => dependencies[id] || { default: stub },
    module,
    module.exports,
    (callback, delay) => {
      const timer = { callback, delay };
      timers.add(timer);
      return timer;
    },
    timer => timers.delete(timer)
  );
  return module.exports.default;
}

async function setup(t, from = 'home', guide = false) {
  const calls = { list: [], stats: [] };
  const timers = new Set();
  const state = Vue.observable({ bizId: 101, guide });
  const request = type => (params, options) => {
    let resolve, reject;
    const promise = new Promise((yes, no) => {
      resolve = yes;
      reject = no;
    });
    calls[type].push({ params, options, resolve, reject });
    return promise;
  };
  const TableStore = load(
    fs.readFileSync(path.join(root, 'src/monitor-pc/pages/collector-config/store.ts'), 'utf8'),
    {
      'monitor-common/utils/timezone': { formatWithTimezone: value => value },
    },
    timers
  );
  const component = load(
    descriptor.script.content,
    {
      '@blueking/fork-resize-detector': { addListener() {}, removeListener() {} },
      'monitor-api/modules/collecting': {
        collectConfigList: request('list'),
        fetchCollectConfigStat: request('stats'),
      },
      'monitor-common/utils': { commonPageSizeGet: () => 10 },
      'throttle-debounce': { debounce: (_, callback) => Object.assign(callback, { cancel() {} }) },
      vuex: { createNamespacedHelpers: () => ({ mapMutations: () => ({}) }) },
      '../../common/introduce': {
        default: { data: { 'collect-config': {} }, getShowGuidePageByRoute: () => state.guide },
      },
      '../../mixins/authorityMixin': { default: () => ({}) },
      './store.ts': { default: TableStore },
    },
    timers
  );
  const runtimeErrors = [];
  Vue.config.errorHandler = error => runtimeErrors.push(error);
  const collector = {
    ...component,
    ...renderOptions,
    beforeCreate() {
      this.$t = this.$tc = value => value;
      this.$store = {
        getters: {
          get bizId() {
            return state.bizId;
          },
          bizList: [],
          lang: 'zh',
        },
      };
      this.authority = { MANAGE_AUTH: true };
    },
  };
  const router = new VueRouter({
    mode: 'abstract',
    base: '/',
    routes: [
      ...['home', 'plugin-manager', 'service-classify', 'collect-config-detail'].map(name => ({
        path: `/${name}`,
        name,
        component: stub,
      })),
      { path: '/collect-config', name: 'collect-config', component: collector, meta: { navId: 'collect-config' } },
    ],
  });
  const app = new Vue({
    router,
    data: { containerKey: 0 },
    render(h) {
      return h('div', { key: this.containerKey }, [h('keep-alive', [h('router-view')])]);
    },
  }).$mount(document.createElement('div'));
  t.after(() => {
    app.$destroy();
    assert.deepEqual(runtimeErrors, []);
  });
  await router.push({ name: from });
  await flush();
  const current = () => router.currentRoute.matched[0].instances.default;
  const settle = async (index = calls.list.length - 1, rows = []) => {
    calls.stats[index].resolve(types);
    calls.list[index].resolve(listResponse(rows));
    await flush();
  };
  return { app, router, calls, state, timers, current, settle };
}

test('same-route container rebuild loads both sections for the new business', async t => {
  const s = await setup(t);
  await s.router.push({ name: 'collect-config' });
  await flush();
  await s.settle();
  const first = s.current();
  s.state.bizId = 202;
  s.app.containerKey += 1;
  await flush();
  assert.notEqual(s.current(), first);
  assert.equal(s.calls.list.length, 2);
  assert.equal(s.calls.stats.length, 2);
  assert.equal(s.calls.list[1].params.bk_biz_id, 202);
  await s.settle();
  assert.equal(s.current().listLoading, false);
  assert.equal(s.current().statsLoading, false);
  assert.equal(s.current().showTableSkeleton, false);
  assert.equal(s.current().emptyType, 'empty');
});

test('first navigation prepares the ID filter before starting one request round', async t => {
  const s = await setup(t);
  await s.router.push({ name: 'collect-config', query: { id: '303' } });
  await flush();
  assert.equal(s.current().panel.keyword, 'ID: 303');
  assert.equal(s.calls.list.length, 1);
  assert.equal(s.calls.stats.length, 1);
  assert.deepEqual(s.calls.list[0].params.search, { id: ' 303' });
  await s.settle();
});

for (const [from, params, keyword, search] of [
  ['service-classify', { serviceCategory: 'example-class' }, '分类example-class', { fuzzy: '分类example-class' }],
  ['plugin-manager', { pluginId: 'example-plugin' }, '插件ID:example-plugin', { plugin_id: 'example-plugin' }],
]) {
  test(`entry from ${from} prepares filters before loading`, async t => {
    const s = await setup(t, from);
    await s.router.push({ name: 'collect-config', params });
    await flush();
    assert.equal(s.current().panel.keyword, keyword);
    assert.equal(s.calls.list.length, 1);
    assert.equal(s.calls.stats.length, 1);
    assert.deepEqual(s.calls.list[0].params.search, search);
    await s.settle();
  });
}

test('cached return from details retains filters and loads exactly one new round', async t => {
  const s = await setup(t);
  await s.router.push({ name: 'collect-config' });
  await flush();
  await s.settle();
  const vm = s.current();
  vm.panel.keyword = 'retained-filter';
  vm.panel.active = 1;
  vm.panel.itemActive = 'stoppedNum';
  const poll = [...s.timers][0];
  assert.equal(poll.delay, 1000);
  await s.router.push({ name: 'collect-config-detail' });
  await flush();
  assert.equal(s.timers.size, 0);
  poll.callback();
  assert.equal(s.calls.list.length, 1);
  await s.router.push({ name: 'collect-config' });
  await flush();
  assert.equal(s.current(), vm);
  assert.equal(vm.panel.keyword, 'retained-filter');
  assert.equal(vm.panel.active, 1);
  assert.equal(vm.panel.itemActive, 'stoppedNum');
  assert.equal(s.calls.list.length, 2);
  assert.equal(s.calls.stats.length, 2);
  assert.deepEqual(s.calls.list[1].params.search, {
    fuzzy: 'retained-filter',
    collect_type: 'Script',
    status: 'STOPPED',
  });
  await s.settle();
});

test('the list deep link still enters matching details after activation loads rows', async t => {
  const s = await setup(t);
  await s.router.push({ name: 'collect-config', query: { id: '303' } });
  await flush();
  await s.settle(0, [config()]);
  assert.equal(s.router.currentRoute.name, 'collect-config-detail');
  assert.equal(s.router.currentRoute.params.id, 303);
  assert.equal(s.calls.list.length, 1);
  assert.equal(s.calls.stats.length, 1);
});

test('a guide-only page performs no list or statistics requests', async t => {
  const s = await setup(t, 'home', true);
  await s.router.push({ name: 'collect-config' });
  await flush();
  assert.equal(s.current().showGuidePage, true);
  assert.equal(s.calls.list.length, 0);
  assert.equal(s.calls.stats.length, 0);
});

test('leaving cancels both requests; delayed old responses cannot finish a new round', async t => {
  const s = await setup(t);
  await s.router.push({ name: 'collect-config' });
  await flush();
  const vm = s.current();
  await s.router.push({ name: 'home' });
  await flush();
  assert.equal(s.calls.list[0].options.signal.aborted, true);
  assert.equal(s.calls.stats[0].options.signal.aborted, true);
  s.state.bizId = 202;
  await s.router.push({ name: 'collect-config' });
  await flush();
  assert.equal(s.current(), vm);
  await s.settle(0, [config(303)]);
  assert.equal(vm.listLoading, true);
  assert.equal(vm.statsLoading, true);
  assert.equal(vm.table.data.length, 0);
  assert.equal(s.calls.list[1].params.bk_biz_id, 202);
  await s.settle(1, [config(404, 202)]);
  assert.equal(vm.table.data[0].id, 404);
  assert.equal(vm.listLoading, false);
  assert.equal(vm.statsLoading, false);
  assert.equal(s.timers.size, 1);
});

test('both API failures end skeletons and expose the existing retry states', async t => {
  const s = await setup(t);
  await s.router.push({ name: 'collect-config' });
  await flush();
  s.calls.list[0].reject(new Error('list unavailable'));
  s.calls.stats[0].reject(new Error('statistics unavailable'));
  await flush();
  assert.equal(s.current().listLoading, false);
  assert.equal(s.current().statsLoading, false);
  assert.equal(s.current().showTableSkeleton, false);
  assert.equal(s.current().statsError, true);
  assert.equal(s.current().emptyType, '500');
  assert.equal(s.timers.size, 0);
});
