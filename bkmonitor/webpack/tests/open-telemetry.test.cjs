const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { createRequire } = require('node:module');
const test = require('node:test');
const ts = require('typescript');

const projectRoot = path.resolve(__dirname, '..');
const configFile = path.join(projectRoot, 'src/monitor-pc/open-telemetry.ts');
const appRequire = createRequire(configFile);
const Vue = appRequire('vue');
const Vuex = appRequire('vuex');
const VueRouter = appRequire('vue-router');
const adapter = appRequire('@blueking/open-telemetry/vue-router3');
Vue.use(Vuex);
Vue.use(VueRouter);

const configCode = ts.transpileModule(fs.readFileSync(configFile, 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText;

function harness(t, options = {}) {
  const calls = { actions: [], events: [], errors: [], timings: [], console: [], updates: [] };
  const oldHandler = Vue.config.errorHandler;
  Vue.config.errorHandler = options.errorHandler;
  const owner = {
    rum: { enabled: true, endpoint: 'https://rum.example.com' },
    location: { origin: 'https://monitor.example.com', href: 'https://monitor.example.com/?bizId=1#/trace/rum' },
    username: 'test-user', footer_version: 'test-version', bk_tenant_id: 'test-tenant',
    console: { error: (...args) => calls.console.push(args) },
    ...options.window,
  };
  const store = new Vuex.Store({
    state: {
      bizId: '',
      bizIdMap: new Map([
        [1, { space_uid: 'bkcc__1', space_type_id: 'bkcc' }],
        [2, { space_uid: 'bkci__2', space_type_id: 'bkci' }],
      ]),
    },
    getters: { bizId: state => state.bizId, bizIdMap: state => state.bizIdMap },
    mutations: {
      'app/SET_BIZ_ID': (state, id) => { state.bizId = id; },
      'app/SET_APP_STATE': (state, data) => Object.assign(state, data),
      unrelated: () => {},
    },
  });
  const router = new VueRouter({ mode: 'abstract', routes: [{ path: '/trace/rum', component: {} }] });
  class RumSpy {
    constructor(config) { this.config = config; }
    reportAction(event) { calls.actions.push(event); }
    reportCustomEvent(event) { calls.events.push(event); }
    reportError(error, context) { calls.errors.push({ error, context }); }
    addTiming(name) { calls.timings.push(name); }
    isViewActive() { return Boolean(this.config.tracking.view.source.getCurrent()); }
  }
  const module = { exports: {} };
  new Function('require', 'module', 'exports', 'window', 'URL', 'process', configCode)(
    name => {
      if (name === '@blueking/open-telemetry') return { BkOpenTelemetry: RumSpy };
      if (name === '@blueking/open-telemetry/vue-router3') return adapter;
      if (name === 'vue') return { default: Vue };
      throw new Error(`Unexpected dependency: ${name}`);
    }, module, module.exports, owner, URL, { env: { NODE_ENV: 'test' } }
  );
  const instance = module.exports.initOpenTelemetry(router, store, options.apiBaseUrl);
  const plugin = instance?.config.extensions.plugins[0];
  const start = () => plugin?.init({
    setRuntimeAttributes(attributes) {
      calls.updates.push(attributes);
    },
  });
  const stop = () => plugin?.shutdown();
  t.after(() => { stop(); Vue.config.errorHandler = oldHandler; });
  return { calls, owner, store, router, instance, start, stop, exports: module.exports };
}

test('SDK disabled or missing endpoint installs no integration', t => {
  const h = harness(t, { window: { rum: { enabled: false, endpoint: 'https://rum.example.com' } } });
  assert.equal(h.instance, undefined);
  h.owner.rum = { enabled: true };
  assert.equal(h.exports.initOpenTelemetry(h.router, h.store), undefined);
  h.store.commit('app/SET_BIZ_ID', 1);
  assert.equal(h.calls.updates.length, 0);
});

test('all requested collectors are enabled and tracing retains the actual API path', t => {
  const h = harness(t, { apiBaseUrl: 'https://api.example.com/monitor/' });
  const tracking = h.instance.config.tracking;
  assert.equal(tracking.error.captureConsole, true);
  assert.equal(tracking.cspViolation, true);
  assert.equal(tracking.websocket, true);
  assert.equal(tracking.device, undefined);
  assert.equal(tracking.longTask, true);
  assert.deepEqual(tracking.request.allowedTracingUrls, ['https://monitor.example.com', 'https://api.example.com/monitor/']);
  assert.deepEqual(tracking.request.excludedUrls, tracking.view.excludedActivityUrls);
  assert.equal(h.exports.initOpenTelemetry(h.router, h.store), h.instance);
});

test('relative API base resolves to the project origin', t => {
  const h = harness(t, { apiBaseUrl: '/api/monitor/' });
  assert.deepEqual(h.instance.config.tracking.request.allowedTracingUrls, [
    'https://monitor.example.com', 'https://monitor.example.com/api/monitor/',
  ]);
});

test('URL redaction keeps route paths and removes credentials, queries and anchors', t => {
  const h = harness(t);
  const redact = h.instance.config.privacy.redactUrl;
  assert.equal(
    redact('https://user:pass@monitor.example.com/app/?external=value#/trace/rum?internal=value#anchor'),
    'https://monitor.example.com/app/#/trace/rum'
  );
  assert.equal(redact('/share/example?key=value#section'), 'https://monitor.example.com/share/***');
  assert.equal(redact('/app/#/share/example?key=value'), 'https://monitor.example.com/app/#/share/***');
  assert.equal(redact('/app/#!/trace/rum#anchor'), 'https://monitor.example.com/app/#!/trace/rum');
  assert.equal(redact('wss://socket.example.com/ws?key=value'), 'wss://socket.example.com/ws');
  assert.equal(redact(''), '');
  assert.equal(redact('https://[invalid'), '');
});

test('switch actions retain business IDs without adding business, space or tenant to runtime attributes', t => {
  const h = harness(t);
  h.start();
  h.store.commit('app/SET_APP_STATE', { bizId: 1 });
  assert.equal(h.calls.actions.length, 0);
  h.store.commit('app/SET_BIZ_ID', 2);
  h.store.commit('app/SET_BIZ_ID', 2);
  h.store.commit('unrelated');
  h.stop();
  h.store.commit('app/SET_BIZ_ID', 1);
  assert.deepEqual(h.calls.actions, [
    { name: 'switch_business', attributes: { 'bk.previous_biz_id': 1, 'bk.target_biz_id': 2 } },
  ]);
  for (const update of h.calls.updates) {
    for (const key of ['bk.biz_id', 'bk.space_uid', 'bk.tenant_id']) {
      assert.equal(Object.hasOwn(update, key), false, key);
    }
  }
});

test('Vue errors preserve the original handler and suppress only its duplicate console error', t => {
  const decisions = [];
  let h;
  const original = (error, vm, info) => decisions.push({
    error, vm, info,
    sent: h.instance.config.tracking.beforeSend({ attributes: { 'error.source': 'console' } }, { type: 'error', error }),
  });
  h = harness(t, { errorHandler: original });
  h.start();
  const error = new Error('render failure');
  const parent = new Vue({ name: 'Root' });
  const child = new Vue({ name: 'Chart', parent });
  Vue.config.errorHandler(error, child, 'render');
  assert.equal(h.calls.errors.length, 1);
  assert.equal(h.calls.errors[0].error, error);
  assert.equal(h.calls.errors[0].context.componentStack, 'Chart\nRoot');
  assert.deepEqual(h.calls.errors[0].context.attributes, { 'error.framework': 'vue', 'vue.info': 'render' });
  assert.equal(decisions[0].sent, false);
  assert.equal(decisions[0].vm, child);
  assert.notEqual(h.instance.config.tracking.beforeSend({ attributes: { 'error.source': 'console' } }, { type: 'error', error }), false);
  h.stop();
  assert.equal(Vue.config.errorHandler, original);
});

test('default Vue error handler keeps local logging and shutdown preserves a newer handler', t => {
  const h = harness(t);
  h.start();
  const error = new Error('mounted failure');
  Vue.config.errorHandler(error, null, 'mounted');
  assert.equal(h.calls.errors.length, 1);
  assert.deepEqual(h.calls.console, [[error]]);
  const replacement = () => {};
  Vue.config.errorHandler = replacement;
  h.stop();
  assert.equal(Vue.config.errorHandler, replacement);
});

test('app ready waits for navigation and Vue tick, then reports once across collection restart', async t => {
  const h = harness(t);
  h.start();
  assert.equal(h.calls.events.length, 0);
  await h.router.push('/trace/rum');
  await Vue.nextTick();
  assert.deepEqual(h.calls.timings, ['app_ready']);
  assert.deepEqual(h.calls.events, [{ name: 'app_ready' }]);
  h.stop();
  h.start();
  await Vue.nextTick();
  assert.equal(h.calls.events.length, 1);
  h.store.commit('app/SET_APP_STATE', { bizId: 1 });
  h.store.commit('app/SET_BIZ_ID', 2);
  assert.equal(h.calls.actions.length, 1);
});

test('shutdown before initial navigation does not report a stale readiness event', async t => {
  const h = harness(t);
  h.start();
  h.stop();
  await h.router.push('/trace/rum');
  await Vue.nextTick();
  assert.equal(h.calls.events.length, 0);
  assert.equal(h.calls.timings.length, 0);
});

test('strategy success reports before navigation without changing the disabled-SDK flow', () => {
  const file = path.join(projectRoot, 'src/monitor-pc/pages/strategy-config/strategy-config-set.tsx');
  const ast = ts.createSourceFile(file, fs.readFileSync(file, 'utf8'), ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  const component = ast.statements.find(node => ts.isClassDeclaration(node));
  const method = component.members.find(node => ts.isMethodDeclaration(node) && node.name.getText(ast) === 'handleSave');
  const code = ts.transpileModule(`const page = { ${method.getText(ast)} }; return page.handleSave;`, {
    compilerOptions: { target: ts.ScriptTarget.ES2022 },
  }).outputText;
  for (const name of ['strategy-config-edit', 'strategy-config-add', 'strategy-config-clone']) {
    const calls = [];
    const sdk = { reportAction: event => calls.push(event), addTiming: name => calls.push(name) };
    const save = new Function('bkOTInstance', code)(sdk);
    const page = { needCheck: true, $route: { name }, $router: { push: target => calls.push(target) } };
    save.call(page);
    assert.deepEqual(calls, [
      { name: 'strategy_save', attributes: { 'strategy.operation': name === 'strategy-config-edit' ? 'edit' : 'create' } },
      'strategy_saved', { name: 'strategy-config' },
    ]);
    assert.equal(page.needCheck, false);
  }
  const targets = [];
  const disabledSave = new Function('bkOTInstance', code)(undefined);
  const page = { needCheck: true, $router: { push: target => targets.push(target) } };
  disabledSave.call(page);
  assert.deepEqual(targets, [{ name: 'strategy-config' }]);
  assert.equal(page.needCheck, false);
});
