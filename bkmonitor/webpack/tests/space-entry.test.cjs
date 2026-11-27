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
    if (name === 'basic') resolve(response);
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
  return { window, location, entry, requests, states, mounts, messages, pinia, mount, start };
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

test('old full backend restores recent business and skips the second directory download', async () => {
  const response = { BK_BIZ_ID: 17, SPACE_LIST: [space(17), space(18)] };
  const h = setup({ url: '#/settings', recent: '18', response });
  h.mount('monitor-pc');
  await flush();
  assert.equal(h.location.searchParams.get('bizId'), '18');
  assert.deepEqual(h.requests.map(r => r.name), ['basic']);
  const landed = setup({ response });
  landed.mount('monitor-pc');
  await flush();
  assert.deepEqual(landed.window.space_list.map(s => s.id), [17, 18]);
  assert.deepEqual(landed.requests.map(r => r.name), ['basic', 'extra']);
});

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

for (const vue3 of [false, true]) {
  test((vue3 ? 'Vue3' : 'Vue2') + ' directory hydration preserves edits in an open selector', () => {
    const file = vue3 ? 'trace/components/space-select/space-selector.tsx' : 'monitor-pc/components/space-select/space-select.tsx';
    const ast = ts.createSourceFile(file, fs.readFileSync(path.join(source, file), 'utf8'), ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
    let method;
    function visit(node) {
      if ((ts.isMethodDeclaration(node) || ts.isFunctionDeclaration(node)) && node.name?.getText(ast) === 'initLocalSpaceList') method = node;
      ts.forEachChild(node, visit);
    }
    visit(ast);
    const spaces = [space(17), space(18)];
    const selected = [];
    const write = value => selected.push([...value]);
    const globals = {
      props: { value: [17], spaceList: spaces }, localValue: { value: [18] }, isOpen: { value: true },
      localSpaceList: { value: [] }, getSpaceList: list => [...list], handleWatchValue: write, setPaginationData() {},
      window: { space_list_state: 'full' },
    };
    const body = ts.transpileModule('function init() ' + method.body.getText(ast), {
      compilerOptions: { target: ts.ScriptTarget.ES2022 },
    }).outputText;
    const run = new Function(...Object.keys(globals), body + '\nreturn init;')(...Object.values(globals));
    run.call({ ...globals, spaceList: spaces, value: [17], localValue: [18], isOpen: true });
    assert.deepEqual(selected, [[18]]);
  });
}
