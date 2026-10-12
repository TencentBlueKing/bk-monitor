const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const ts = require('typescript');

const root = path.join(__dirname, '..');
const transpile = file => ts.transpileModule(fs.readFileSync(path.join(root, file), 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText;
const runtimeCode = transpile('src/trace/micro-app-runtime.ts');
const setterKeys = ['__VUE_INSTANCE_SETTERS__', '__VUE_SSR_SETTERS__'];

function harness({ shared = true } = {}) {
  const originalToString = function hostToString() {};
  const prototype = {};
  Object.defineProperty(prototype, 'toString', {
    value: originalToString, writable: true, configurable: true, enumerable: false,
  });
  let nextTimer = 0;
  const timers = new Map();
  const raw = {
    _: { owner: 'host' },
    setTimeout(handler, delay, ...args) {
      const id = ++nextTimer;
      timers.set(id, { handler, delay, args });
      return id;
    },
    clearTimeout(id) { timers.delete(id); },
  };
  for (const key of setterKeys) raw[key] = [() => {}];
  if (shared) raw['__core-js_shared__'] = { inspectSource: () => {}, state: new WeakMap() };
  const target = Object.assign(Object.create(raw), { rawWindow: raw });
  const module = { exports: {} };
  new Function('exports', 'module', 'Function', runtimeCode)(module.exports, module, { prototype });
  const capture = module.exports.prepareMicroAppRuntime(target);
  const traceToString = function traceToString() {};
  prototype.toString = traceToString;
  if (!shared) target['__core-js_shared__'] = { inspectSource: () => {}, state: new WeakMap() };
  const traceSetters = [];
  for (const key of setterKeys) {
    const setter = () => {};
    traceSetters.push(setter);
    raw[key].push(setter);
  }
  target.webpackChunktrace = [];
  target.webpackChunktrace.push = (() => {}).bind(null);
  return { raw, target, capture, prototype, originalToString, traceToString, traceSetters, timers };
}

test('sandbox exports are renewed without changing host libraries or extension hooks', () => {
  const h = harness();
  const hostContext = { owner: 'host' };
  const extensionHook = { emit() {} };
  h.raw.__VUE_DEVTOOLS_KIT_CONTEXT__ = hostContext;
  h.raw.__VUE_DEVTOOLS_GLOBAL_HOOK__ = extensionHook;
  const release = h.capture();
  h.target.__VUE_DEVTOOLS_KIT_CONTEXT__ = { owner: 'trace' };
  h.target.__VUE_DEVTOOLS_HOOK = { owner: 'trace' };
  // Lazy chunks install these exports after static imports have been captured.
  h.target.filterCSS = () => {};
  h.target.filterXSS = () => {};
  h.target.i18n = { locale: 'en' };
  h.target.regeneratorRuntime = { owner: 'trace' };
  release();
  for (const key of ['__VUE_DEVTOOLS_KIT_CONTEXT__', '__VUE_DEVTOOLS_HOOK', 'filterCSS', 'filterXSS', 'i18n', 'regeneratorRuntime']) {
    assert.equal(h.target[key], undefined);
  }
  assert.equal(h.raw.__VUE_DEVTOOLS_KIT_CONTEXT__, hostContext);
  assert.equal(h.target.__VUE_DEVTOOLS_GLOBAL_HOOK__, extensionHook);
});

test('unmount cancels sandbox timeouts while keeping host cache expiry and later timer owners', () => {
  const h = harness();
  const release = h.capture();
  const cacheTimer = h.raw.setTimeout(() => {}, 60000);
  const completed = h.target.setTimeout(function(value) {
    assert.equal(this, h.raw);
    assert.equal(value, 'argument');
  }, 10, 'argument');
  const task = h.timers.get(completed);
  h.timers.delete(completed);
  task.handler(...task.args);
  const canceled = h.target.setTimeout(() => {}, 20);
  h.target.clearTimeout(canceled);
  const pending = h.target.setTimeout(() => {}, 120000);
  const laterTimeout = () => 42;
  h.target.setTimeout = laterTimeout;
  release();
  assert.equal(h.timers.has(pending), false);
  assert.equal(h.timers.has(cacheTimer), true);
  assert.equal(h.target.setTimeout, laterTimeout);
  assert.equal(h.target.clearTimeout, h.raw.clearTimeout);
});

test('cleanup drops only the injected data identity captured by this mount', () => {
  const h = harness();
  h.capture()();
  const module = { exports: {} };
  new Function('exports', 'module', 'Function', runtimeCode)(module.exports, module, { prototype: h.prototype });
  const firstData = { host: 'example.test' };
  h.target.__BK_WEWEB_DATA__ = firstData;
  module.exports.prepareMicroAppRuntime(h.target)()();
  assert.equal(h.target.__BK_WEWEB_DATA__, undefined);
  h.target.__BK_WEWEB_DATA__ = firstData;
  const release = module.exports.prepareMicroAppRuntime(h.target)();
  const nextData = { host: 'next.example.test' };
  h.target.__BK_WEWEB_DATA__ = nextData;
  release();
  assert.equal(h.target.__BK_WEWEB_DATA__, nextData);
});

test('restores shared helpers before a later host library can capture the trace runtime', () => {
  const h = harness();
  const pool = h.target['__core-js_shared__'];
  const inspect = pool.inspectSource;
  const state = pool.state;
  const descriptor = Object.getOwnPropertyDescriptor(h.prototype, 'toString');
  const release = h.capture();
  assert.equal(h.prototype.toString, h.originalToString);
  assert.deepEqual(Object.getOwnPropertyDescriptor(h.prototype, 'toString'), {
    ...descriptor, value: h.originalToString,
  });
  assert.equal(pool.inspectSource, inspect);
  assert.equal(pool.state, state);
  // This models the host's late core-js native-function export, which outlives the app.
  pool['native-function-to-string'] = h.prototype.toString;
  release();
  assert.equal(pool['native-function-to-string'], h.originalToString);
});

test('removes newly installed helpers without replacing the shared state pool', () => {
  const h = harness({ shared: false });
  const pool = h.target['__core-js_shared__'];
  const state = pool.state;
  pool['native-function-to-string'] = h.traceToString;
  const release = h.capture();
  assert.equal(Object.hasOwn(pool, 'inspectSource'), false);
  assert.equal(Object.hasOwn(pool, 'native-function-to-string'), false);
  assert.equal(pool.state, state);
  const otherInspect = () => {};
  pool.inspectSource = otherInspect;
  release();
  assert.equal(pool.inspectSource, otherInspect);
});

test('unmount removes only frozen trace setter identities and releases sandbox references', () => {
  const h = harness();
  const hostDash = h.raw._;
  assert.equal(h.target._, undefined);
  assert.equal(h.raw._, hostDash);
  const release = h.capture();
  const lateSetters = setterKeys.map(key => {
    const setter = () => {};
    h.raw[key].push(setter);
    return setter;
  });
  h.target._ = { owner: 'trace' };
  release();
  release();
  for (let i = 0; i < setterKeys.length; i++) {
    assert.equal(h.raw[setterKeys[i]].includes(h.traceSetters[i]), false);
    assert.equal(h.raw[setterKeys[i]].includes(lateSetters[i]), true);
    assert.equal(h.raw[setterKeys[i]].length, 2);
  }
  assert.equal(h.target._, undefined);
  assert.equal(h.raw._, hostDash);
  assert.equal(h.target.webpackChunktrace.push, Array.prototype.push);
});

test('later owners of the function, shared pool and chunk callback survive cleanup', () => {
  const h = harness();
  const release = h.capture();
  const laterToString = () => {};
  const laterPush = () => {};
  const laterPool = { inspectSource: () => {}, 'native-function-to-string': laterToString };
  h.prototype.toString = laterToString;
  h.target.webpackChunktrace.push = laterPush;
  h.target['__core-js_shared__'] = laterPool;
  release();
  assert.equal(h.prototype.toString, laterToString);
  assert.equal(h.target.webpackChunktrace.push, laterPush);
  assert.equal(h.target['__core-js_shared__'], laterPool);
  assert.equal(laterPool['native-function-to-string'], laterToString);
});

test('recreated modules do not accumulate setter or JSONP callback chains', () => {
  const h = harness();
  h.capture()();
  for (let cycle = 0; cycle < 16; cycle++) {
    const module = { exports: {} };
    new Function('exports', 'module', 'Function', runtimeCode)(module.exports, module, { prototype: h.prototype });
    const capture = module.exports.prepareMicroAppRuntime(h.target);
    for (const key of setterKeys) h.raw[key].push(() => {});
    h.prototype.toString = () => {};
    h.target.webpackChunktrace.push = (() => {}).bind(h.target.webpackChunktrace.push);
    const release = capture();
    h.target._ = { previous: h.target._ };
    release();
    for (const key of setterKeys) assert.equal(h.raw[key].length, 1);
    assert.equal(h.target.webpackChunktrace.push, Array.prototype.push);
    assert.equal(h.prototype.toString, h.originalToString);
  }
});

async function entryHarness(powered) {
  const calls = [];
  const window = { __POWERED_BY_BK_WEWEB__: powered, showLoginModal: () => {} };
  let unmount;
  window.__BK_WEWEB_DATA__ = { setUnmountCallback: callback => { unmount = callback; } };
  const app = {
    config: {},
    use() { return this; }, mount() { return this; },
    unmount() { calls.push('unmount'); throw new Error('unmount failure'); },
  };
  const module = { exports: {} };
  const requireDependency = id => {
    if (id === './public-path') return { captureMicroAppRuntime: powered ? () => () => calls.push('release') : undefined };
    if (id === 'vue') return { createApp: () => app };
    if (id === 'monitor-api/api') return { default: { model: { enhancedContext() {
      calls.push(window.showLoginModal === login ? 'api-after-login' : 'api-before-login');
      return new Promise(() => {});
    } } } };
    if (id === 'monitor-common/utils') return { getUrlParam: () => undefined, parseBizId: () => 7 };
    if (id === 'monitor-pc/common/global-login') { calls.push('login'); window.showLoginModal = login; return {}; }
    if (id === 'monitor-api/utils/index') return { setVue() {} };
    if (id === './store/modules/authority') return { useAuthorityStore: () => ({}) };
    return {};
  };
  function login() {}
  new Function('require', 'module', 'exports', 'window', 'process', transpile('src/trace/index.ts'))(
    requireDependency, module, module.exports, window, { env: { NODE_ENV: 'production', defaultBizId: 7 } }
  );
  await new Promise(resolve => setImmediate(resolve));
  return { calls, window, unmount };
}

test('micro entry keeps the host login bridge and releases runtime even if Vue unmount throws', async () => {
  const h = await entryHarness(true);
  assert.deepEqual(h.calls, []);
  assert.throws(h.unmount, /unmount failure/);
  assert.deepEqual(h.calls, ['unmount', 'release']);
});

test('standalone entry installs the login handler before the first context request', async () => {
  const h = await entryHarness(false);
  assert.deepEqual(h.calls, ['login', 'api-after-login']);
});

test('host releases the cached data callback even if the child unmount throws', async () => {
  const source = ts.transpileModule(fs.readFileSync(path.join(root, 'src/monitor-pc/pages/host/host.tsx'), 'utf8'), {
    compilerOptions: {
      module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, experimentalDecorators: true,
      jsx: ts.JsxEmit.React,
    },
  }).outputText;
  const module = { exports: {} };
  let data;
  const calls = [];
  const Component = value => value;
  Component.registerHooks = () => {};
  const ai = { enableAiAssistant: true, setCustomFallbackShortcut: value => calls.push(value) };
  const requireDependency = id => {
    if (id === 'vue-property-decorator') return { Component, Prop: () => () => {}, Ref: () => () => {} };
    if (id === 'vue-tsx-support') return { Component: class {} };
    if (id === '@blueking/bk-weweb') return {
      loadApp: async props => { data = props.data; }, mount: () => {}, unmount: () => calls.push('sdk-unmount'),
    };
    if (id === '../../common/introduce') return { default: { getShowGuidePageByRoute: () => false } };
    if (id === './host-url') return { buildHostAppUrl: () => 'https://example.test/trace/' };
    if (id === '@/store/modules/ai-whale') return { default: ai };
    return {};
  };
  new Function('require', 'module', 'exports', 'window', 'location', 'process', 'setTimeout', source)(
    requireDependency, module, module.exports, {}, { origin: 'https://example.test' },
    { env: { NODE_ENV: 'production' } }, () => 1
  );
  const host = new module.exports.default();
  host.$route = { meta: {} };
  host.$store = { getters: {}, commit() {} };
  host.hostApp = { shadowRoot: {} };
  await host.mounted();
  assert.equal(data.enableAiAssistant, true);
  data.handleAIBluekingShortcut('shortcut');
  data.setUnmountCallback(() => { calls.push('child-unmount'); throw new Error('unmount failure'); });
  assert.throws(() => host.beforeDestroy(), /unmount failure/);
  assert.equal(data.setUnmountCallback, undefined);
  assert.equal(host.unmountCallback, undefined);
  assert.equal(host.microAppData, undefined);
  assert.deepEqual(calls, ['shortcut', 'child-unmount', 'sdk-unmount']);
  const nextData = host.hostData;
  assert.equal(typeof nextData.setUnmountCallback, 'function');
  ai.enableAiAssistant = false;
  assert.equal(nextData.enableAiAssistant, false);
});
