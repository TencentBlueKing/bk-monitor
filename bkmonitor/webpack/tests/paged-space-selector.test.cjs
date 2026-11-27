const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const ts = require('typescript');
const Vue = require('../src/trace/node_modules/vue');

const source = '../src/trace/components/space-select/';
const directory = 'monitor-common/utils/space-directory';
const t = value => value;
const tick = () => new Promise(resolve => setImmediate(resolve));
const row = id => ({
  bk_biz_id: id,
  space_name: 'space ' + id,
  space_type_id: 'bkcc',
  space_id: String(id),
  type_name: '业务',
});
const page = (items = [], next_cursor = null, partial = false) => ({ items, next_cursor, partial });
const alert = (id, data = true) => ({ bk_biz_id: id, bk_biz_name: 'alert ' + id, has_data: data });
const cache = new Map();
function load(file, deps, globals) {
  if (!cache.has(file)) {
    const src = fs.readFileSync(path.resolve(__dirname, file), 'utf8');
    const code = ts.transpileModule(src, {
      fileName: file,
      compilerOptions: {
        module: ts.ModuleKind.CommonJS,
        target: ts.ScriptTarget.ES2022,
        jsx: ts.JsxEmit.React,
        jsxFactory: 'h',
      },
    }).outputText;
    cache.set(file, new Function('require', 'exports', 'window', 'document', 'history', 'setTimeout', 'h', code));
  }
  const result = {};
  cache.get(file)(id => deps[id] ?? {}, result, ...globals);
  return result;
}
function fixture(overrides = {}, options = {}) {
  const events = [],
    admissions = [],
    urls = [],
    calls = [],
    timers = [];
  const win = {
    i18n: { t },
    space_list_state: 'deferred',
    space_list_page_supported: options.support !== false,
    location: { pathname: '/' },
  };
  let click, keyboard, unmount;
  const doc = {
    addEventListener(_name, fn) {
      click = fn;
    },
  };
  const store = { bizId: 2 };
  const query = kind => params => {
    assert.ok(params && params.mode === 'page', 'every directory query is bounded');
    return new Promise((resolve, reject) => calls.push({ kind, params, resolve, reject }));
  };
  const globals = [
    win,
    doc,
    { replaceState: (...args) => urls.push(args) },
    fn => timers.push(fn),
    (type, props, ...children) => ({ type, props, children: children.flat(Infinity) }),
  ];
  const deps = {
    vue: {
      ...Vue,
      onUnmounted: fn => {
        unmount = fn;
      },
      useTemplateRef: () => ({ value: { focus() {}, clientWidth: 0, scrollWidth: 0 } }),
    },
    '@vueuse/core': {
      useDebounceFn: fn => fn,
      useEventListener: (_win, _name, fn) => {
        keyboard = fn;
        return () => {};
      },
    },
    'bkui-vue': { Button: 'button' },
    'vue-i18n': { useI18n: () => ({ t }) },
    'vue-router': { useRoute: () => ({ fullPath: '/trace/alarm' }) },
    'vue-tippy': { useTippy: () => ({ show() {}, hide() {}, destroy() {} }) },
    'monitor-api/modules/commons': { listSpaces: query('allowed') },
    'monitor-api/modules/home': { bizWithAlertStatistics: query('alert') },
    'monitor-common/utils/space-entry': {
      canSwitchSpace: async id => {
        admissions.push(id);
        return true;
      },
    },
    '../../store/modules/app': { useAppStore: () => store },
    './utils': { getEventPaths: () => [], SPACE_TYPE_MAP: { default: { light: {} } } },
  };
  deps[directory] = load('../src/' + directory + '.ts', deps, globals);
  deps['./typing'] = load(source + 'typing.ts', deps, globals);
  deps['./paged-space-options'] = load(source + 'paged-space-options.ts', deps, globals);
  const component = load(source + 'space-selector.tsx', deps, globals).default;
  const props = Vue.reactive({
    remote: true,
    spaceList: [],
    value: [],
    currentSpace: null,
    multiple: true,
    ...overrides,
  });
  const scope = Vue.effectScope();
  const state = scope.run(() =>
    Vue.proxyRefs(component.setup(props, { emit: (event, value) => events.push([event, value]) }))
  );
  const draw = () => component.render.call({ ...props, ...state });
  const clickText = label => {
    function find(node) {
      if (node?.type === 'button' && node.children.includes(label)) return node;
      return node?.children?.map(find).find(Boolean);
    }
    const found = find(draw());
    assert.ok(found, 'visible action ' + label);
    return found.props.onClick();
  };
  return {
    state,
    props,
    calls,
    events,
    urls,
    admissions,
    store,
    clickText,
    open() {
      state.handleMousedown();
      timers.splice(0).forEach(fn => fn());
    },
    close() {
      click({});
    },
    destroy() {
      unmount();
      scope.stop();
    },
    key(key) {
      keyboard({ key, preventDefault() {}, stopPropagation() {} });
    },
    ids() {
      return state.pagination.data.map(item => item.id);
    },
    take(kind, params = {}) {
      const index = calls.findIndex(
        call => call.kind === kind && Object.entries(params).every(([key, val]) => call.params[key] === val)
      );
      assert.notEqual(index, -1, JSON.stringify({ kind, params, calls: calls.map(call => call.params) }));
      return calls.splice(index, 1)[0];
    },
  };
}

test('closed selector hydrates only saved IDs, eligible alert names and unresolved IDs stay independent', async () => {
  const f = fixture({ value: [7, 8, 9, 10, -1], hasAuthApply: true, needAuthorityOption: true });
  f.take('allowed', { bk_biz_ids: '7,8,9,10' }).resolve(page([row(7)]));
  await tick();
  f.take('alert', { bk_biz_ids: '8,9,10' }).resolve(page([alert(8), alert(9, false)], null, true));
  await tick();
  assert.deepEqual(f.calls, []);
  assert.deepEqual(
    f.state.valueStrList.map(a => a.name),
    ['-我有权限的空间-', 'space 7', 'alert 8', 'alert 9', '#10']
  );
  assert.equal(f.state.lookupError, true);
  assert.deepEqual(f.store.noAuthBizIds, [9]);
  assert.equal(f.state.canMakeCurrent(7), true);
  for (const id of [8, 9, 10]) assert.equal(f.state.canMakeCurrent(id), false);
  f.destroy();
});

test('keyboard and visible continuation work across empty pages and independent alarm and view cursors', async () => {
  const f = fixture({ hasAuthApply: true });
  assert.deepEqual(f.calls, []);
  f.open();
  f.take('allowed').resolve(page([], 'A'));
  f.take('alert').resolve(page([], 'B'));
  await tick();
  assert.deepEqual(f.ids(), []);
  const next = f.clickText('加载更多...');
  f.take('allowed', { cursor: 'A' }).resolve(page([row(7)], 'C'));
  f.take('alert', { cursor: 'B' }).resolve(page([alert(8)]));
  await next;
  assert.deepEqual(f.ids(), [7, 8]);
  f.key('ArrowDown');
  assert.equal(f.state.highlightId, 8);
  f.key('ArrowDown');
  f.take('allowed', { cursor: 'C' }).resolve(page([row(11)]));
  await tick();
  assert.equal(f.state.highlightId, 11);
  f.key('Enter');
  assert.equal(f.state.isOpen, true);
  f.state.handleSelectOption(f.state.pagination.data.find(item => item.id === 8));
  f.state.handleSearchInput('fresh');
  f.take('alert', { query: 'fresh' }).resolve(page());
  f.take('allowed', { query: 'fresh' }).resolve(page([row(12)]));
  await tick();
  assert.deepEqual(f.ids(), [12]);
  f.state.handleSelectOption(f.state.pagination.data[0]);
  f.close();
  assert.deepEqual(
    f.events.at(-1)[1].sort((a, b) => a - b),
    [8, 11, 12]
  );
  assert.deepEqual(f.admissions, []);
  f.destroy();
});

test('single selection of a received-alert business cannot promote it to the main business', async () => {
  const f = fixture({
    hasAuthApply: true,
    multiple: false,
    currentSpace: 2,
    spaceList: [{ ...row(2), id: 2 }],
    isAutoSelectCurrentSpace: true,
  });
  f.open();
  f.take('allowed', { bk_biz_ids: '2' }).resolve(page([row(2)]));
  f.take('allowed', { bk_biz_ids: undefined }).resolve(page([row(2)]));
  f.take('alert').resolve(page([alert(7)]));
  await tick();
  const received = f.state.pagination.data.find(item => item.id === 7);
  f.state.handleSetCurBiz(received);
  assert.equal(f.state.localCurrentSpace, 2);
  f.state.handleSelectOption(received);
  await tick();
  assert.deepEqual(f.events, [['change', [7]]]);
  assert.deepEqual(f.admissions, []);
  assert.deepEqual(f.urls, []);
  f.destroy();
});

test('reopening discards late pages; sentinel remains exclusive and type/search start new cursors', async () => {
  const f = fixture({ value: [2], spaceList: [{ ...row(2), id: 2 }], needAuthorityOption: true });
  f.open();
  f.take('allowed', { bk_biz_ids: '2' }).resolve(page([row(2)]));
  f.take('allowed', { bk_biz_ids: undefined }).resolve(page());
  await tick();
  f.state.handleSearchInput('old');
  const stale = f.take('allowed', { query: 'old' });
  f.close();
  f.open();
  f.take('allowed', { bk_biz_ids: '2' }).resolve(page([row(2)]));
  f.take('allowed', { bk_biz_ids: undefined }).resolve(page([row(7)], 'next'));
  await tick();
  f.state.handleSelectOption(f.state.pagination.data.find(item => item.id === 7));
  f.state.handleSearchType('bcs');
  f.take('allowed', { type: 'bcs', cursor: undefined }).resolve(page([row(17)]));
  stale.resolve(page([row(99)]));
  await tick();
  assert.deepEqual(f.ids(), [17]);
  f.state.handleSearchType('bcs');
  f.take('allowed', { type: undefined }).resolve(page());
  await tick();
  f.state.handleSelectOption(f.state.pagination.data.find(item => item.id === -1));
  f.close();
  assert.deepEqual(f.events.at(-1), ['change', [-1]]);
  f.open();
  const last = f.take('allowed');
  f.destroy();
  last.resolve(page([row(99)]));
  await tick();
  assert.ok(!f.ids().includes(99));
});

test('local subset and older services continue to use the consumer-supplied list', () => {
  for (const [remote, support] of [
    [false, true],
    [true, false],
  ]) {
    const f = fixture({ remote, spaceList: [{ ...row(2), id: 2 }] }, { support });
    f.open();
    assert.deepEqual(f.ids(), [2]);
    assert.deepEqual(f.calls, []);
    f.destroy();
  }
});

test('retry verifies a selected business on reopen even when the parent still supplies its previous grant', async () => {
  const f = fixture({ value: [7], hasAuthApply: true, spaceList: [{ ...row(7), id: 7 }] });
  assert.equal(f.state.canMakeCurrent(7), false);
  f.take('allowed', { bk_biz_ids: '7' }).resolve(page([row(7)]));
  await tick();
  assert.equal(f.state.canMakeCurrent(7), true);
  f.open();
  f.take('allowed', { bk_biz_ids: '7' }).resolve(page());
  f.take('allowed', { bk_biz_ids: undefined }).reject(new Error('temporarily unavailable'));
  f.take('alert', { bk_biz_ids: undefined }).resolve(page([alert(8)]));
  await tick();
  f.take('alert', { bk_biz_ids: '7' }).resolve(page([], null, true));
  await tick();
  assert.equal(f.state.canMakeCurrent(7), false);
  assert.deepEqual(f.ids(), [7, 8]);
  f.clickText('部分空间未能确认，请重试');
  f.take('allowed', { bk_biz_ids: '7' }).resolve(page());
  f.take('allowed', { bk_biz_ids: undefined }).resolve(page([row(11)]));
  f.take('alert', { bk_biz_ids: undefined }).resolve(page());
  await tick();
  f.take('alert', { bk_biz_ids: '7' }).resolve(page([alert(7)]));
  await tick();
  assert.equal(f.state.lookupError || f.state.pageError, false);
  assert.equal(f.state.valueStr, 'alert 7');
  assert.equal(f.state.canMakeCurrent(7), false);
  f.destroy();
});

test('incomplete normal authorization keeps confirmed rows and retries unresolved IDs before looking up alert-only names', async () => {
  const f = fixture({ value: [7, 8], hasAuthApply: true });
  f.take('allowed', { bk_biz_ids: '7,8' }).resolve(page([row(7)], null, true));
  await tick();
  assert.deepEqual(f.calls, []);
  assert.equal(f.state.lookupError, true);
  assert.deepEqual(
    f.state.valueStrList.map(item => item.name),
    ['space 7', '#8']
  );
  assert.deepEqual(f.store.noAuthBizIds, []);
  f.open();
  f.take('allowed', { bk_biz_ids: '7,8' }).resolve(page([row(7)], null, true));
  f.take('allowed', { bk_biz_ids: undefined }).resolve(page([row(9)], null, true));
  f.take('alert', { bk_biz_ids: undefined }).resolve(page());
  await tick();
  assert.equal(f.state.pageError, true);
  assert.deepEqual(f.ids(), [7, 8, 9]);
  assert.equal(f.state.canMakeCurrent(8), false);
  f.clickText('部分空间未能确认，请重试');
  f.take('allowed', { bk_biz_ids: '8' }).resolve(page([row(8)]));
  f.take('allowed', { bk_biz_ids: undefined }).resolve(page([row(9)]));
  f.take('alert', { bk_biz_ids: undefined }).resolve(page());
  await tick();
  assert.deepEqual(f.calls, []);
  assert.equal(f.state.pageError || f.state.lookupError, false);
  assert.equal(f.state.canMakeCurrent(8), true);
  f.destroy();
});
