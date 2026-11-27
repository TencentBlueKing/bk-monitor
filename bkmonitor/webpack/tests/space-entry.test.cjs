const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const ts = require('typescript');

const source = path.resolve(__dirname, '../src');
const compiled = new Map();
const flush = () => new Promise(resolve => setImmediate(resolve));

function load(file, globals, dependencies) {
  if (!compiled.has(file)) {
    compiled.set(file, ts.transpileModule(fs.readFileSync(path.join(source, file), 'utf8'), {
      compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS },
    }).outputText);
  }
  const exports = {};
  new Function('require', 'exports', ...Object.keys(globals), compiled.get(file))(
    id => dependencies[id] || {}, exports, ...Object.values(globals)
  );
  return exports;
}

const space = id => ({ bk_biz_id: id, space_name: String(id), space_uid: 'space__' + id });
const basic = (id, access = 'allowed') => ({
  SPACE_LIST_STATE: 'deferred', SPACE_ACCESS: access, BK_BIZ_ID: id,
  SPACE_LIST: access === 'allowed' ? [space(id)] : [],
});

function setup({ url = '?bizId=17#/settings', recent, build, token, child, response = basic(17) } = {}) {
  const location = new URL(url, 'https://example.test/');
  const window = { location, site_url: '/', i18n: { t: key => key }, __BK_WEWEB_DATA__: { token, $baseStore: child } };
  const requests = [], states = [], mounts = [], messages = [];
  const root = { replaceChildren(...nodes) { messages.push(nodes[0].textContent); } };
  const globals = {
    window, location, history: { replaceState(_state, _title, href) { location.href = href; } },
    localStorage: { getItem: () => recent, setItem() {} },
    process: { env: { defaultBizId: build } },
    document: { body: { querySelector: () => null }, getElementById: () => root,
      createElement: () => ({ setAttribute() {} }) },
  };
  const getUrlParam = k => location.searchParams.get(k);
  const utils = load('monitor-common/utils/index.ts', globals, { './constant': { LOCAL_BIZ_STORE_KEY: 'recent' }, './utils': { getUrlParam } });
  const fetch = name => (params, config) => new Promise((resolve, reject) => {
    requests.push({ name, params, config, resolve, reject });
    if (name === 'basic' && response !== null) resolve(typeof response === 'function' ? response(params) : response);
  });
  const entry = load('monitor-common/utils/space-entry.ts', globals, {
    './index': utils, './utils': { getUrlParam }, 'monitor-api/modules/model': { enhancedContext: fetch('basic') },
    'monitor-api/modules/commons': { listSpaces: fetch('directory') },
    'monitor-api/utils/index': { bkMessage: e => messages.push(e.message) },
  });
  const store = { commit: (_type, data) => states.push(data) };
  const pinia = {};
  const vue3 = { config: {}, use() { return this; }, mount() { mounts.push('app'); }, unmount() {} };
  class Vue {
    static config = {};
    constructor(config) {
      if (config?.el) mounts.push(config.router ? 'app' : 'pending');
    }
    $destroy() {}
  }
  const deps = {
    vue: { default: Vue, createApp: () => vue3 }, 'monitor-api/api': { default: { model: { enhancedContext: fetch('extra') } } },
    'monitor-api/axios/axios': { default: { defaults: {} } }, 'monitor-api/utils/index': { setVue() {} },
    'monitor-common/service-worker/service-worker': { immediateRegister() {} },
    'monitor-common/utils': { ...utils, getUrlParam }, 'monitor-common/utils/space-entry': entry,
    'monitor-common/utils/global-feature-map': { isAidevEmbed: () => true },
    './store/store': { default: store }, './store/modules/app': { useAppStore: () => pinia },
    './store/modules/authority': { useAuthorityStore: () => ({}) }, './router/router': { default: {} },
    './open-telemetry': { initOpenTelemetry() {} }, 'monitor-common/utils/iframe-bridge': { initIframeBroadcast() {} },
    './i18n/dayjs': { updateTimezone() {} },
    './common/user-display-name': { userDisplayNameConfigure() {} },
    'monitor-pc/common/user-display-name': { userDisplayNameConfigure() {} },
  };
  function mount(shell) {
    load(shell + '/index.ts', globals, deps);
  }
  function start(data) {
    window.space_list = utils.mergeSpaceList(data.SPACE_LIST);
    window.bk_biz_id = window.cc_biz_id = data.BK_BIZ_ID;
    window.space_access = data.SPACE_ACCESS;
    window.space_list_state = data.SPACE_LIST_STATE;
    return entry.initializeSpaceEntry(data);
  }
  function createRouter(Router = require('vue-router'), Vue = require('vue')) {
    const routeNames = ['share', 'event-center', 'settings', 'no-business'];
    const routes = routeNames.map(name => ({ name, path: '/' + name }));
    routes.push({ name: 'alarm-center', path: '/trace/alarm-center' });
    const routeDeps = Object.fromEntries(['dashboard', 'data-retrieval', 'event', 'integrated', 'manager', 'others',
      'scenes', 'platform-setting', 'dashboard/email-subscriptions'].map(name => ['./' + name, { default: [] }]));
    return load('monitor-pc/router/router.ts', globals, {
      ...deps, ...routeDeps, vue: { default: Vue }, 'vue-router': { default: Router },
      'monitor-common/utils/utils': { getUrlParam }, './home': { default: routes },
      '../store/store': { default: { ...store, getters: { bizList: [] } } },
      '../store/modules/report-log': { default: { reportRouteLog() {} } },
      './router-config': { isInCommonRoute: () => false, getRouteRootName() {}, getRouteConfigById() {} },
    }).default;
  }
  return { window, location, entry, requests, states, mounts, messages, pinia, mount, start, createRouter };
}

for (const shell of ['monitor-pc', 'trace', 'apm', 'fta-solutions']) {
  test(shell + ' mounts with the admitted space, then fills the directory', async () => {
    const h = setup();
    h.mount(shell);
    assert.deepEqual(h.requests.map(r => r.name), ['basic']);
    assert.equal(h.requests[0].params.include_space_list, 0);
    assert.equal(h.requests[0].params.bk_biz_id, 17);
    await flush();
    assert.deepEqual(h.mounts, ['app']);
    assert.deepEqual(h.window.space_list.map(s => s.id), [17]);
    const directory = h.requests.find(r => r.name === 'directory');
    assert.deepEqual(directory.params, { show_all: false, show_detail: false });
    directory.resolve([space(18), space(17)]);
    await flush();
    assert.deepEqual((shell === 'trace' ? h.pinia.bizList : h.states.at(-1).bizList).map(s => s.id), [17, 18]);
  });
}

test('sentinels and cache are preferences, negative space IDs and UIDs are explicit', async () => {
  for (const [url, recent, build, explicit, preferred, uid] of [
    ['?bizId=-1#/', '-12', '7', undefined, -12], ['?bizId=0#/', 'bad', '7', undefined, 7],
    ['?bizId=-19#/', '12', '7', -19], ['?bizId=11&space_uid=a#/', '12', '7', undefined, undefined, 'a'],
  ]) {
    const h = setup({ url, recent, build });
    await h.entry.getBasicSpaceContext();
    const { params, config } = h.requests[0];
    assert.deepEqual([params.bk_biz_id, params.preferred_biz_id, params.space_uid], [explicit, preferred, uid]);
    assert.equal(config.needBiz, false);
  }
});

test('stale cache and user default cannot override the business admitted by basic', () => {
  const h = setup({ url: '?bizId=-1#/settings', recent: '99' });
  h.window.default_biz_id = 44;
  assert.equal(h.start(basic(-12)), -12);
  assert.equal(h.location.searchParams.get('bizId'), '-12');
  assert.equal(h.location.hash, '#/settings');
});

for (const shell of ['monitor-pc', 'trace', 'apm', 'fta-solutions']) {
  test(shell + ' redirects legacy implicit entries before mounting business-specific basic and extra', async () => {
    for (const [recent, build, expected] of [['18', '17', 18], [null, '18', 18], ['99', null, 17]]) {
      const response = ({ bk_biz_id = 17 }) => ({
        BK_BIZ_ID: bk_biz_id, SPACE_LIST: [space(17), space(18)], ENABLE_ISSUE_AI_ANALYSIS: bk_biz_id === 18,
      });
      const first = setup({ url: '#/settings', recent, build, response });
      first.mount(shell);
      await flush();
      assert.equal(first.requests[0].params.preferred_biz_id, Number(recent || build));
      assert.deepEqual(first.requests.map(r => r.name), ['basic']);
      assert.deepEqual(first.mounts, []);
      assert.equal(first.window.cc_biz_id, 17);
      assert.equal(first.location.searchParams.get('bizId'), String(expected));
      const landing = setup({ url: first.location.href, recent, build, response });
      landing.mount(shell);
      await flush();
      assert.deepEqual(landing.requests.map(r => [r.name, r.params.bk_biz_id]), [['basic', expected], ['extra', expected]]);
      assert.deepEqual(landing.mounts, ['app']);
      assert.equal(landing.window.bk_biz_id, expected);
      assert.equal(landing.window.cc_biz_id, expected);
      assert.equal(landing.window.enable_issue_ai_analysis, expected === 18);
      assert.deepEqual(landing.window.space_list.map(s => s.id), [17, 18]);
    }
  });
}

test('denial and no spaces use the no-business route, missing space and service failure remain distinguishable', () => {
  for (const [url, id, access] of [['?bizId=-12#/settings', -12, 'denied'], ['#/settings', -1, 'denied']]) {
    const h = setup({ url });
    assert.equal(h.start(basic(id, access)), id);
    assert.equal(h.location.hash, '#/no-business');
  }
  for (const [status, message] of [['not_found', '空间不存在'], ['error', '空间权限检查失败，请重试']]) {
    const h = setup({ url: '?space_uid=missing#/settings' });
    assert.equal(h.start(basic(-1, status)), false);
    assert.deepEqual(h.messages, [message]);
    assert.equal(h.location.searchParams.get('space_uid'), 'missing');
  }
});

for (const [url, token] of [['?bizId=-12#/share/example'], ['?bizId=-12#/trace/alarm-center/detail/example'], ['?bizId=-12#/settings', 'sample']]) {
  test('public entry keeps its target ' + url, () => {
    const h = setup({ url, token });
    assert.equal(h.start(basic(-12, 'denied')), -12);
    assert.equal(h.location.pathname + h.location.search + h.location.hash, '/' + url);
    assert.equal(h.entry.isAidevPermissionPending(basic(-12, 'denied')), false);
  });
}

test('AIDev mounts the waiting page only for a pending admission', async () => {
  for (const [access, pending] of [['allowed', false], ['denied', true], ['not_found', false], ['error', false]]) {
    const h = setup({ response: basic(17, access) });
    h.mount('apm');
    await flush();
    assert.equal(h.mounts.includes('pending'), pending);
    assert.equal(h.mounts.includes('app'), access === 'allowed');
  }
});

test('APM child follows Vuex changes and detaches the subscription on unmount', () => {
  let notify, unmount, detached = false;
  const child = { getters: { bizList: [space(17)] }, watch(pick, callback) {
    notify = list => callback(pick({}, { bizList: list }));
    return () => { detached = true; };
  } };
  const h = setup({ child });
  h.window.__POWERED_BY_BK_WEWEB__ = true;
  h.window.rawWindow = { bk_biz_id: 17 };
  h.window.__BK_WEWEB_DATA__.setUnmountCallback = fn => { unmount = fn; };
  h.mount('apm');
  notify([space(17), space(18)]);
  assert.equal(h.states.at(-1).bizList.length, 2);
  unmount();
  assert.equal(detached, true);
  assert.deepEqual(h.requests, []);
});

test('a failed directory request preserves the current space and can be retried', async () => {
  const h = setup();
  h.mount('monitor-pc');
  await flush();
  h.requests.find(r => r.name === 'directory').reject(new Error('unavailable'));
  await flush();
  assert.equal(h.window.space_list_state, 'deferred');
  assert.deepEqual(h.window.space_list.map(s => s.id), [17]);
  assert.deepEqual(h.messages, ['空间目录加载失败，请刷新页面重试']);
  const retry = h.window.loadSpaceDirectory();
  h.requests.at(-1).resolve([space(17), space(18)]);
  assert.equal((await retry).length, 2);
});

test('a business switch requests basic for the new target before committing it', async () => {
  const h = setup({ response: basic(18, 'denied') });
  h.start(basic(17));
  assert.equal(await h.entry.canSwitchSpace(17), true);
  assert.equal(h.requests.length, 0);
  assert.equal(await h.entry.canSwitchSpace(18), false);
  assert.equal(h.requests[0].params.bk_biz_id, 18);
  assert.equal(h.requests[0].params.context_type, 'basic');
  assert.equal(h.location.hash, '#/no-business');
});

test('Vue Router 3 redirects a denied public entry leaving for a protected page and retains the page on failure', async () => {
  const Router = require('vue-router');
  for (const status of ['denied', 'not_found', 'error', 'allowed']) {
    const h = setup({ url: '?bizId=17#/share', response: null });
    h.start(basic(17, 'denied'));
    const router = h.createRouter();
    await router.push('/share');
    const pending = router.push('/settings').catch(error => error);
    const request = h.requests.at(-1);
    assert.equal(request.params.bk_biz_id, 17);
    if (status === 'error') request.reject(new Error('unavailable'));
    else request.resolve(basic(17, status));
    const result = await pending;
    if (status === 'error') {
      assert.ok(Router.isNavigationFailure(result, Router.NavigationFailureType.aborted));
      assert.deepEqual(h.messages, ['空间权限检查失败，请重试']);
      assert.equal(router.currentRoute.name, 'share');
    } else if (status === 'allowed') {
      assert.equal(router.currentRoute.name, 'settings');
    } else {
      assert.ok(Router.isNavigationFailure(result, Router.NavigationFailureType.redirected));
      assert.equal(router.currentRoute.name, 'no-business');
    }
  }
});

test('Vue Router 3 discards a late admission when a newer public navigation finishes', async () => {
  const Router = require('vue-router');
  for (const status of ['denied', 'error', 'allowed']) {
    const h = setup({ url: '?bizId=17#/share', response: null });
    h.start(basic(17, 'denied'));
    const router = h.createRouter();
    await router.push('/share');
    const pending = router.push('/settings').catch(error => error);
    await router.push('/event-center');
    h.requests.at(-1).resolve(basic(17, status));
    assert.ok(Router.isNavigationFailure(await pending, Router.NavigationFailureType.cancelled));
    assert.equal(router.currentRoute.name, 'event-center');
    assert.deepEqual(h.messages, []);
  }
});

// Exercise Vue Router's installed HashHistory, including its native popstate listener.
function createHashRouter(h) {
  const entries = [h.location.href];
  const events = new EventTarget();
  let index = 0;
  h.window.navigator = { userAgent: 'test' };
  h.window.addEventListener = events.addEventListener.bind(events);
  h.window.removeEventListener = events.removeEventListener.bind(events);
  h.window.history = {
    get length() { return entries.length; },
    pushState(_state, _title, href) {
      h.location.href = href;
      entries.splice(++index, Infinity, h.location.href);
    },
    replaceState(_state, _title, href) {
      h.location.href = href;
      entries[index] = h.location.href;
    },
    go(offset) {
      if (index + offset < 0 || index + offset >= entries.length) return;
      index += offset;
      h.location.href = entries[index];
      events.dispatchEvent(new Event('popstate'));
    },
  };
  const module = { exports: {} };
  const script = fs.readFileSync(require.resolve('vue-router'), 'utf8');
  new Function('window', 'document', 'module', 'exports', script)(
    h.window, { querySelector: () => null }, module, module.exports
  );
  const Vue = require('vue');
  const localVue = Object.assign(Vue.extend(), { config: Vue.config });
  const router = h.createRouter(module.exports, localVue);
  assert.equal(router.mode, 'hash');
  router.history.setupListeners();
  return router;
}

for (const [path, childQuery] of [
  ['/share?filter=critical', ''],
  ['/trace/alarm-center?filter=critical', ''],
  ['/trace/alarm-center', '?from=now-7d&to=now&filterMode=ui&currentPage=2'],
]) {
  test('Back restores the complete public URL after denied navigation from ' + path + childQuery, async () => {
    const h = setup({ url: '?bizId=17#/event-center', response: basic(17, 'denied') });
    h.start(basic(17, 'denied'));
    const router = createHashRouter(h);
    await router.push(path);
    if (childQuery) {
      // Trace writes filters directly to browser history, without updating the host route.
      h.window.history.replaceState(null, '', h.location.href + childQuery);
      assert.equal(router.currentRoute.fullPath, path);
    }
    const original = h.location.href;
    const length = h.window.history.length;
    await router.push('/settings').catch(() => {});
    assert.equal(router.currentRoute.name, 'no-business');
    assert.equal(h.window.history.length, length + 1);
    router.back();
    await flush();
    assert.equal(h.location.href, original);
    assert.equal(router.currentRoute.fullPath, path + childQuery);
  });
}

test('denial replaces a protected source instead of leaving a Back loop', async () => {
  const h = setup({ url: '?bizId=17#/event-center', response: basic(18, 'denied') });
  h.start(basic(17));
  const router = createHashRouter(h);
  await router.push('/event-center?filter=older');
  await router.push('/settings?tab=old');
  const url = new URL(h.location.href);
  url.searchParams.set('bizId', '18');
  h.window.history.replaceState(null, '', url.href);
  const length = h.window.history.length;
  await router.push('/settings?tab=new').catch(() => {});
  assert.equal(router.currentRoute.name, 'no-business');
  assert.equal(h.window.history.length, length);
  router.back();
  await flush();
  assert.equal(router.currentRoute.fullPath, '/event-center?filter=older');
});

test('Back onto a now-denied target replaces that entry and preserves forward history', async () => {
  const h = setup({ url: '?bizId=17#/event-center', response: basic(17, 'denied') });
  h.start(basic(17));
  const router = createHashRouter(h);
  await router.push('/event-center?filter=older');
  await router.push('/settings');
  await router.push('/share?filter=current');
  h.start(basic(17, 'denied'));
  const length = h.window.history.length;
  router.back();
  await flush();
  assert.equal(router.currentRoute.name, 'no-business');
  assert.equal(h.window.history.length, length);
  router.back();
  await flush();
  assert.equal(router.currentRoute.fullPath, '/event-center?filter=older');
  router.forward();
  await flush();
  router.forward();
  await flush();
  assert.equal(router.currentRoute.fullPath, '/share?filter=current');
});

test('a space UID and a conflicting business ID always use the space UID and preserve the route', () => {
  for (const data of [basic(17), { BK_BIZ_ID: 17, SPACE_LIST: [space(17), space(18)] }]) {
    const h = setup({ url: '/monitor/?space_uid=space__17&bizId=18&lang=en#/settings' });
    assert.equal(h.start(data), 17);
    assert.equal(h.location.pathname, '/monitor/');
    assert.equal(h.location.hash, '#/settings');
    assert.equal(h.location.searchParams.get('lang'), 'en');
    assert.equal(h.location.searchParams.get('space_uid'), 'space__17');
    assert.equal(h.location.searchParams.get('bizId'), null);
  }
});

function selectorMethods(vue3) {
  const file = vue3 ? 'trace/components/space-select/space-selector.tsx' : 'monitor-pc/components/space-select/space-select.tsx';
  const ast = ts.createSourceFile(file, fs.readFileSync(path.join(source, file), 'utf8'), ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  const methods = {};
  function visit(node) {
    if ((ts.isMethodDeclaration(node) || ts.isFunctionDeclaration(node)) && node.body) {
      methods[node.name.getText(ast)] = node.body.getText(ast);
    }
    if (ts.isCallExpression(node) && node.expression.getText(ast) === 'onUnmounted') {
      methods.destroyed = node.arguments[0].body.getText(ast);
    }
    ts.forEachChild(node, visit);
  }
  visit(ast);
  return methods;
}

for (const vue3 of [false, true]) {
  const methods = selectorMethods(vue3);
  test((vue3 ? 'Vue3' : 'Vue2') + ' directory hydration preserves edits in an open selector', () => {
    const spaces = [space(17), space(18)];
    const selected = [];
    const write = value => selected.push([...value]);
    const globals = {
      props: { value: [17], spaceList: spaces }, localValue: { value: [18] }, isOpen: { value: true },
      localSpaceList: { value: [] }, getSpaceList: list => [...list], handleWatchValue: write, setPaginationData() {},
      window: { space_list_state: 'full' },
    };
    const body = ts.transpileModule('function init() ' + methods.initLocalSpaceList, {
      compilerOptions: { target: ts.ScriptTarget.ES2022 },
    }).outputText;
    const run = new Function(...Object.keys(globals), body + '\nreturn init;')(...Object.values(globals));
    run.call({ ...globals, spaceList: spaces, value: [17], localValue: [18], isOpen: true });
    assert.deepEqual(selected, [[18]]);
  });

  test((vue3 ? 'Vue3' : 'Vue2') + ' only commits the selection from the latest closed popup', async () => {
    for (const interrupted of ['reopen', 'unmount']) {
      for (const status of ['allowed', 'denied', 'error']) {
        const h = setup({ response: null });
        h.start(basic(17));
        const emitted = [], updated = [];
        const emit = (_event, value) => emitted.push(value);
        const props = { currentSpace: 17, value: [17], isAutoSelectCurrentSpace: true };
        const noop = () => {};
        const list = { value: [] }, current = { value: 17 };
        const route = { fullPath: '/settings' };
        const history = { replaceState(_state, _title, href) { h.location.href = new URL(href, h.location.href).href; } };
        const vars = {
          props, emit, specialIds: [], canSwitchSpace: h.entry.canSwitchSpace, needCurSpace: { value: true },
          selectRef: {}, localValue: { value: [18] }, localSpaceList: list, localCurrentSpace: current, isOpen: { value: false },
          searchValue: {}, searchTypeId: {}, highlightId: {}, setTimeout: noop, useTippy: () => ({ hide: noop }),
          unbindKeyboard: noop, bindKeyboard: noop, sortSpaceList: noop, setPaginationData: noop, resetHighlight: noop,
          triggerRef: noop, route, history, window: h.window, appStore: { set bizId(id) { updated.push(id); } },
        };
        const ctx = { ...vars, ...props, selectionSession: 0, $bkPopover: () => ({}), localSpaceList: [],
          localCurrentSpace: 17, localValue: [18], isOpen: false, needCurSpace: true, $emit: emit,
          $store: { commit: (_mutation, id) => updated.push(id) }, $route: route };
        const code = `let selectionSession = 0, popInstance, controller;
          function open() ${methods.handleMousedown}
          async function close() ${methods.handlePopoverHidden}
          function unmount() ${methods.destroyed}
          function resetCurBiz(curSpace) ${methods.resetCurBiz}
          return { open, close, unmount, resetCurBiz };`;
        const controls = new Function(...Object.keys(vars), ts.transpile(code, { target: ts.ScriptTarget.ES2022 }))(...Object.values(vars));
        ctx.resetCurBiz = controls.resetCurBiz;
        controls.open.call(ctx);
        const pending = controls.close.call(ctx);
        assert.equal(h.requests.at(-1).params.bk_biz_id, 18);
        if (interrupted === 'unmount') controls.unmount.call(ctx);
        else {
          controls.open.call(ctx);
          ctx.localValue = vars.localValue.value = [19];
        }
        h.requests.at(-1).resolve(basic(18, status));
        await pending;
        assert.deepEqual(updated, []);
        assert.deepEqual(emitted, []);
        assert.deepEqual(h.messages, []);
        assert.equal(h.location.searchParams.get('bizId'), '17');
        assert.equal(h.location.hash, '#/settings');
        if (interrupted === 'reopen') {
          const latest = controls.close.call(ctx);
          assert.equal(h.requests.at(-1).params.bk_biz_id, 19);
          // A late directory update can reinitialize the closed popover from its props.
          ctx.localValue = vars.localValue.value = [17];
          h.requests.at(-1).resolve(basic(19));
          await latest;
          assert.deepEqual(updated, [19]);
          assert.equal(h.location.searchParams.get('bizId'), '19');
          assert.deepEqual(emitted, [[19]]);
        }
      }
    }
  });
}
