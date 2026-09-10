const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { test } = require('node:test');
const ts = require('typescript');

// Run production TS/TSX with mocked component boundaries; no network or browser required.
const vue = {
  defineComponent: value => value,
  ref: value => ({ value }),
  computed: getter => ({
    get value() {
      return getter();
    },
  }),
  watch() {},
  nextTick: callback => Promise.resolve().then(callback),
  onUnmounted() {},
};
const h = (type, props, ...children) => ({ type, props, children: children.flat(Infinity) });
function loadSource(file, mocks = {}, globals = {}) {
  const filename = path.resolve(__dirname, '../../src', file);
  const output = ts.transpileModule(fs.readFileSync(filename, 'utf8'), {
    compilerOptions: {
      module: ts.ModuleKind.CommonJS,
      target: ts.ScriptTarget.ES2020,
      jsx: ts.JsxEmit.React,
      jsxFactory: 'h',
      esModuleInterop: true,
    },
    fileName: filename,
  }).outputText;
  const module = { exports: {} };
  vm.runInNewContext(
    output,
    {
      module,
      exports: module.exports,
      h,
      console,
      require(name) {
        if (name === 'vue') return vue;
        if (Object.hasOwn(mocks, name)) return mocks[name];
        throw new Error(`Unmocked import: ${name}`);
      },
      ...globals,
    },
    { filename },
  );
  return module.exports;
}
const routeHelpers = loadSource('global/bk-space-choice/space-switch-route.ts');
const plain = value => JSON.parse(JSON.stringify(value));
const space = { space_uid: 'bkcc__2', bk_biz_id: '2', space_name: 'Target', permission: { view_business: true } };

function initialRoute() {
  return {
    name: 'retrieve',
    params: { indexId: '123' },
    query: {
      spaceUid: 'missing',
      bizId: '99',
      keyword: 'error',
      unionList: '["123","456"]',
      retrieve_type: 'scene',
      scene_active: 'custom',
      'pod[eq]': 'frontend',
      from: 'monitor',
    },
  };
}
test('failed-space recovery preserves the original index and search query without mutating input', () => {
  const route = initialRoute();
  const before = plain(route);
  const location = routeHelpers.buildSpaceRecoveryLocation({ ...route, routeName: route.name, space });
  assert.deepEqual(plain(location), {
    name: 'retrieve',
    params: { indexId: '123' },
    query: { ...route.query, spaceUid: space.space_uid, bizId: '2' },
  });
  assert.deepEqual(route, before);
});
test('legacy unauthorized links recover their query index as a path parameter', () => {
  const location = routeHelpers.buildSpaceRecoveryLocation({
    routeName: 'un-authorized',
    query: { indexId: '123', bkBizId: '99', type: 'space', page_from: 'retrieve', keyword: 'error' },
    space,
  });
  assert.deepEqual(plain(location), {
    name: 'retrieve',
    params: { indexId: '123' },
    query: { keyword: 'error', bizId: '2', spaceUid: space.space_uid },
  });
});
test('missing index stays absent so existing default-index adaptation can run', () => {
  const location = routeHelpers.buildSpaceRecoveryLocation({ routeName: 'retrieve', space });
  assert.deepEqual(plain(location.params), {});
});
test('ordinary scene switching still strips old scene filters and uses the default scene', () => {
  const route = initialRoute();
  const query = routeHelpers.buildSpaceSwitchQuery({ routeName: 'retrieve', query: route.query, space });
  assert.deepEqual(plain(query), {
    spaceUid: space.space_uid,
    bizId: '2',
    retrieve_type: 'scene',
    scene_active: 'k8s',
    from: 'monitor',
  });
  assert.deepEqual(plain(routeHelpers.omitRouteIndexId(route.params)), {});
});
test('homepage renders only unauthorized content until recovery, then retains version selection', () => {
  for (const version of ['v1', 'v3']) {
    const state = { spaceResolveFailed: true };
    const UnAuthorized = {};
    const component = loadSource(
      'views/retrieve-hub.tsx',
      {
        '@/hooks/use-store': () => ({ state }),
        'vue-router/composables': { useRoute: () => initialRoute() },
        '@/views/un-authorized': UnAuthorized,
      },
      { localStorage: { getItem: () => version } },
    ).default;
    const render = component.setup();
    assert.equal(render().type, UnAuthorized);
    assert.equal(render().props.type, 'space');
    state.spaceResolveFailed = false;
    assert.equal(render().type, `retrieve-${version}`);
  }
});

function findNode(node, predicate) {
  if (!node || typeof node !== 'object') return undefined;
  if (predicate(node)) return node;
  return node.children?.map(child => findNode(child, predicate)).find(Boolean);
}
function selectorFixture({ failed = true, spaces = [space] } = {}) {
  const route = initialRoute();
  const storageKeys = new Proxy({}, { get: (_, key) => key });
  const state = {
    spaceResolveFailed: failed,
    spaceUid: 'missing',
    spaceListLoaded: false,
    storage: {},
    indexItem: { retrieve_type: 'scene' },
  };
  const store = {
    state,
    getters: {},
    commit(name, value) {
      if (name === 'updateSpace') state.spaceUid = value;
      if (name === 'updateStorage') Object.assign(state.storage, value);
      if (name === 'updateState') Object.assign(state, value);
    },
  };
  let nextLocation,
    finishNavigation,
    pending,
    listRequests = 0;
  const List = {};
  const component = loadSource(
    'global/bk-space-choice/index.tsx',
    {
      '@/api': {},
      '@/hooks/use-locale': () => ({ t: text => text }),
      '@/hooks/use-nav-menu': {
        useNavMenu: () => ({ mySpaceList: vue.ref(spaces), isFirstLoad: vue.ref(true), checkSpaceChange() {} }),
      },
      '@/preload': {
        getAllSpaceList: () => {
          listRequests++;
        },
      },
      '@/store/constant': { SPACE_TYPE_MAP: {} },
      '@/store/store.type': { BK_LOG_STORAGE: storageKeys },
      'throttle-debounce': {
        debounce:
          (_, callback) =>
          (...args) => {
            pending = callback(...args);
          },
      },
      'vue-router/composables': {
        useRoute: () => route,
        useRouter: () => ({
          push(location) {
            nextLocation = location;
            return new Promise(resolve => {
              finishNavigation = success => {
                if (success) Object.assign(route, plain(location));
                resolve();
              };
            });
          },
        }),
      },
      '../../common/authority-map': { VIEW_BUSINESS: 'view_business' },
      '../../hooks/use-store': () => store,
      '../../hooks/use-list-sort': list => ({ sortList: vue.ref(list), updateList() {}, updateSearchText() {} }),
      '../../mixins/user-store-config': class {},
      './list': List,
      './space-switch-route': routeHelpers,
      './index.scss': {},
    },
    { window: {}, setTimeout() {} },
  ).default;
  const render = component.setup({ isExpand: true, theme: 'dark', isExternalAuth: false }, { emit() {} });
  return {
    state,
    route,
    render,
    List,
    get nextLocation() {
      return nextLocation;
    },
    get listRequests() {
      return listRequests;
    },
    async finish(success) {
      finishNavigation(success);
      await pending;
    },
  };
}
test('unmatched current space still exposes a dropdown and requests the full list', () => {
  const fixture = selectorFixture({ spaces: [] });
  const trigger = findNode(fixture.render(), node => node.props?.class === 'menu-select-name');
  assert.ok(trigger.children.includes('请选择业务'));
  trigger.props.onMousedown();
  assert.equal(fixture.listRequests, 1);
  const list = findNode(fixture.render(), node => node.type === fixture.List);
  assert.ok(list);
  assert.equal(list.props.list.length, 0);
});
for (const succeeds of [true, false]) {
  test(`recovery ${succeeds ? 'mounts only after successful navigation' : 'keeps unauthorized view after failed navigation'}`, async () => {
    const fixture = selectorFixture();
    findNode(fixture.render(), node => node.props?.class === 'menu-select-name').props.onMousedown();
    findNode(fixture.render(), node => node.type === fixture.List).props['on-HandleClickMenuItem'](space);
    assert.equal(fixture.state.spaceResolveFailed, true);
    assert.equal(fixture.nextLocation.params.indexId, '123');
    assert.equal(fixture.nextLocation.query['pod[eq]'], 'frontend');
    await fixture.finish(succeeds);
    assert.equal(fixture.state.spaceResolveFailed, !succeeds);
  });
}
test('ordinary space selection still uses the existing scene reset route', async () => {
  const fixture = selectorFixture({ failed: false });
  findNode(fixture.render(), node => node.props?.class === 'menu-select-name').props.onMousedown();
  findNode(fixture.render(), node => node.type === fixture.List).props['on-HandleClickMenuItem'](space);
  assert.deepEqual(plain(fixture.nextLocation.params), {});
  assert.equal(fixture.nextLocation.query.scene_active, 'k8s');
  assert.equal(fixture.nextLocation.query['pod[eq]'], undefined);
  await fixture.finish(true);
});

function bootstrapCreated(space) {
  const filename = path.resolve(__dirname, '../../src/main.js');
  const source = ts.createSourceFile(filename, fs.readFileSync(filename, 'utf8'), ts.ScriptTarget.Latest, true);
  let created;
  function visit(node) {
    if (ts.isMethodDeclaration(node) && node.name.getText(source) === 'created') created = node;
    ts.forEachChild(node, visit);
  }
  visit(source);
  assert.ok(created, 'bootstrap created hook exists');
  return vm.runInNewContext(`({${created.getText(source)}}).created`, {
    space,
    spaceUid: 'missing',
    bkBizId: '99',
    store: { state: { storage: {} } },
    BK_LOG_STORAGE: {},
    urlArgs: { index_id: '123' },
  });
}
test('bootstrap waits for the resolved homepage and does not change its URL on space failure', () => {
  let ready,
    pushed = [];
  const app = {
    $route: { name: null },
    $router: {
      onReady: callback => {
        ready = callback;
      },
      push: location => pushed.push(location),
    },
  };
  bootstrapCreated(null).call(app);
  assert.equal(pushed.length, 0);
  app.$route = initialRoute();
  ready();
  assert.equal(pushed.length, 0);
});
test('bootstrap preserves legacy non-home authorization handling and original query index', () => {
  let pushed;
  const app = {
    $route: { name: 'un-authorized', params: {}, query: { indexId: '456', keyword: 'error' } },
    $router: {
      onReady: callback => callback(),
      push: location => {
        pushed = location;
      },
    },
  };
  bootstrapCreated(null).call(app);
  assert.equal(pushed.path, '/un-authorized');
  assert.equal(pushed.query.indexId, '456');
  assert.equal(pushed.query.keyword, 'error');
});
