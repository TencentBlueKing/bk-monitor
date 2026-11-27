const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const ts = require('typescript');

const root = path.join(__dirname, '../src');
function transpile(file, modules, window) {
  const { outputText } = ts.transpileModule(readFileSync(path.join(root, file), 'utf8'), {
    compilerOptions: {
      module: ts.ModuleKind.CommonJS,
      target: ts.ScriptTarget.ES2022,
      jsx: ts.JsxEmit.React,
      experimentalDecorators: true,
    },
  });
  const exports = {};
  Function('require', 'exports', 'window', outputText)(id => modules[id] || {}, exports, window);
  return exports;
}
const space = (id, name = String(id)) => ({
  bk_biz_id: id, space_name: name, space_id: String(id), space_type_id: 'bkcc', space_uid: 'bkcc__' + id,
});
function requestQueue() {
  const requests = [];
  const send = (params, config) => new Promise((resolve, reject) => {
    requests.push({ params, config, resolve, reject });
  });
  return { requests, send };
}
function setup(window = { space_list_page_supported: true, i18n: { tc: text => text } }) {
  const normal = requestQueue(), alerts = requestQueue();
  const directory = transpile('monitor-common/utils/space-directory.ts', {
    'monitor-api/modules/commons': { listSpaces: normal.send },
    'monitor-api/modules/home': { bizWithAlertStatistics: alerts.send },
    'bk-magic-vue/lib/utils/pinyin': { default: { isSupported: () => false } },
  }, window);
  return { directory, normal: normal.requests, alerts: alerts.requests, window };
}

test('a page uses one scoped request, shares only the in-flight call and preserves server order', async () => {
  const h = setup();
  const page = h.directory.querySpaceDirectory({ query: 'bj', type: 'bcs' });
  assert.equal(page, h.directory.querySpaceDirectory({ query: 'bj', type: 'bcs' }));
  assert.equal(h.normal.length, 1);
  assert.deepEqual(h.normal[0].params, {
    mode: 'page', query: 'bj', type: 'bcs', page_size: 20, cursor: undefined, bk_biz_ids: undefined, space_uids: undefined, include_demo: undefined,
  });
  assert.deepEqual(h.normal[0].config, { needBiz: false });
  h.normal[0].resolve({ items: [space(-12, '北京'), space(77)], next_cursor: 'cursor-B' });
  assert.deepEqual((await page).items.map(row => [row.id, row.text]), [[-12, '北京'], [77, '77']]);
  const again = h.directory.querySpaceDirectory({ query: 'bj', type: 'bcs' });
  assert.equal(h.normal.length, 2);
  h.normal[1].resolve({ items: [], next_cursor: null });
  await again;
});

test('empty clipped page can continue, and closing/search replacement invalidates a late page', async () => {
  const h = setup(), pager = new h.directory.SpaceDirectoryPager();
  const search = pager.reset({ query: 'A' });
  h.normal[0].resolve({ items: [], next_cursor: 'skip' });
  assert.equal(await search, true);
  assert.equal(pager.hasMore, true);
  const old = pager.next();
  assert.equal(h.normal[1].params.cursor, 'skip');
  const fresh = pager.reset({ query: 'B' });
  h.normal[2].resolve({ items: [space(7)], next_cursor: 'B2' });
  await fresh;
  h.normal[1].resolve({ items: [space(1)], next_cursor: null });
  assert.equal(await old, false);
  assert.deepEqual(pager.items.map(row => row.id), [7]);
  const next = pager.next();
  assert.equal(await pager.next(), false);
  pager.close();
  h.normal[3].resolve({ items: [space(8)], next_cursor: null });
  assert.equal(await next, false);
  assert.deepEqual(pager.items, []);
  assert.equal(h.normal.length, 4);
});

test('saved references go back through the API, preserve pin precedence and never publish a partial list globally', async () => {
  const h = setup(), pager = new h.directory.SpaceDirectoryPager();
  const seed = [space(2)];
  h.window.space_list = seed;
  const search = pager.reset({}, { bkBizIds: [12, 11], spaceUids: ['bkci__pin'] });
  h.normal[0].resolve({ items: [space(2), space(12)], next_cursor: 'next' });
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(h.normal[1].params.bk_biz_ids, '12,11');
  assert.equal(h.normal[2].params.space_uids, 'bkci__pin');
  h.normal[1].resolve({ items: [space(12)], next_cursor: null });
  h.normal[2].resolve({ items: [space(-8)], next_cursor: null });
  await search;
  assert.deepEqual(pager.items.map(s => s.id), [12, -8, 2]);
  assert.equal(h.window.space_list, seed);
  assert.equal(h.normal.length, 3);
});

test('a legacy full-array response supports local pinyin, secondary type and filtered ID pages', async () => {
  const h = setup();
  const rows = [
    { ...space(-5, '北京'), space_code: 'project', space_type_id: 'bkci', py_text: 'beijing', pyf_text: 'bj' },
    { ...space(9), space_code: '', space_type_id: 'bkci' },
    { ...space(-7, '北郊'), space_code: 'ci', space_type_id: 'bkci', py_text: 'beijiao', pyf_text: 'bj' },
  ];
  const a = h.directory.querySpaceDirectory({ query: 'bj', type: 'bcs', pageSize: 1 });
  h.normal[0].resolve(rows);
  const first = await a;
  assert.deepEqual(first.items.map(x => x.id), [-5]);
  const second = await h.directory.querySpaceDirectory({ query: 'bj', type: 'bcs', pageSize: 1, cursor: first.nextCursor });
  assert.deepEqual(second.items.map(x => x.id), [-7]);
  assert.equal(second.nextCursor, null);
  assert.deepEqual((await h.directory.querySpaceDirectory({ bkBizIds: [9] })).items.map(x => x.id), [9]);
  assert.deepEqual((await h.directory.querySpaceDirectory({ bkBizIds: [] })).items, []);
  assert.equal(h.normal.length, 1);
});

test('alert context stays distinct from view permission, including partial results and errors', async () => {
  const h = setup();
  const pager = new h.directory.SpaceDirectoryPager(h.directory.queryAlertSpaceDirectory);
  const job = pager.reset({ bkBizIds: [90, 18] });
  assert.equal(h.alerts[0].params.bk_biz_ids, '90,18');
  assert.equal(h.normal.length, 0);
  h.alerts[0].resolve({ items: [{ bk_biz_id: 90, bk_biz_name: 'target', has_data: true }], next_cursor: 'more', partial: true });
  await job;
  assert.deepEqual(pager.items.map(x => [x.id, x.noAuth, x.hasData]), [[90, true, true]]);
  assert.equal(pager.partial, true);
  const next = pager.next();
  h.alerts[1].reject(new Error('unavailable'));
  await assert.rejects(next);
  assert.equal(pager.failed, true);
  assert.equal(pager.nextCursor, 'more');
  assert.equal(pager.isLoading, false);
});

test('a rolling downgrade during cursor pagination resumes past known records without repeating full reads', async () => {
  const h = setup(), pager = new h.directory.SpaceDirectoryPager();
  const initial = pager.reset({ pageSize: 1 });
  h.normal[0].resolve({ items: [space(1)], next_cursor: 'opaque-from-new-replica' });
  await initial;
  const next = pager.next();
  h.normal[1].resolve([space(1), space(2), space(3)]);
  await next;
  assert.deepEqual(pager.items.map(x => x.id), [1, 2]);
  await pager.next();
  assert.deepEqual(pager.items.map(x => x.id), [1, 2, 3]);
  assert.equal(pager.hasMore, false);
  assert.equal(h.normal.length, 2);
  h.window.uin = 'different-actor';
  const newActor = h.directory.querySpaceDirectory({});
  assert.equal(h.normal.length, 3);
  h.normal[2].resolve({ items: [], next_cursor: null });
  assert.deepEqual((await newActor).items, []);
});

test('legacy FTA objects separate authorized, received-only and unapplied historical targets', async () => {
  const h = setup();
  const business = n => ({ bk_biz_id: n, bk_biz_name: 'space-' + n });
  const all = h.directory.queryAlertSpaceDirectory();
  h.alerts[0].resolve({
    business_list: [business(1), business(2), business(3)],
    business_with_permission: [business(1)],
    business_with_alert: [business(2)],
  });
  assert.deepEqual((await all).items.map(row => [row.id, row.noAuth, row.hasData]), [[2, true, true]]);
  const selected = await h.directory.queryAlertSpaceDirectory({ bkBizIds: [1, 2, 3, 4] });
  assert.deepEqual(selected.items.map(row => [row.id, row.noAuth, row.hasData]), [[2, true, true], [3, true, false]]);
  assert.equal(h.alerts.length, 1);
});

test('failed next request keeps the authorized rows and cursor for retry', async () => {
  const h = setup(), pager = new h.directory.SpaceDirectoryPager();
  const first = pager.reset();
  h.normal[0].resolve({ items: [space(3)], next_cursor: 'next' });
  await first;
  const failed = pager.next();
  h.normal[1].reject(new Error('503'));
  await assert.rejects(failed);
  assert.deepEqual(pager.items.map(row => row.id), [3]);
  assert.equal(pager.nextCursor, 'next');
  const retry = pager.next();
  h.normal[2].resolve({ items: [space(4)], next_cursor: null });
  await retry;
  assert.deepEqual(pager.items.map(row => row.id), [3, 4]);
});

function component(file, h) {
  const decorator = () => () => {};
  const modules = {
    'vue-property-decorator': { Component: C => C, Emit: decorator, Prop: decorator, Ref: decorator, Watch: decorator },
    'vue-tsx-support': { Component: class {} },
    'monitor-common/utils/space-directory': h.directory,
    'monitor-common/utils': { Debounce: decorator },
    'monitor-common/utils/utils': { Debounce: decorator },
    '../biz-select/list': { ETagsType: { BKCC: 'bkcc' } },
    './list': { ETagsType: { BKCC: 'bkcc' } },
    './utils': { SPACE_TYPE_MAP: { default: {} } },
    '../../common/constant': { SPACE_TYPE_MAP: { default: {} }, SPACE_FIRST_CODE_COLOR_MAP: { default: {} } },
  };
  const C = transpile(file, modules, h.window).default;
  const c = new C();
  c.$t = c.$tc = text => text;
  return c;
}

test('Vue2 multi-select preserves checked records across pages and searches; alert-only records stay outside navigation', async () => {
  const h = setup();
  const c = component('monitor-pc/components/space-select/space-select.tsx', h);
  Object.assign(c, { remote: true, hasAuthApply: true, value: [], spaceList: [], multiple: true, isOpen: true });
  const first = c.loadDirectory();
  h.normal[0].resolve({ items: [space(8)], next_cursor: 'v2' });
  h.alerts[0].resolve({ items: [{ bk_biz_id: 19, bk_biz_name: 'received', has_data: true }], next_cursor: null });
  await first;
  const individual = id => c.localSpaceList.find(x => x.id === id);
  c.handleSelectOption(individual(8));
  const next = c.loadDirectory(true);
  h.normal[1].resolve({ items: [space(7)], next_cursor: null });
  await next;
  c.handleSelectOption(individual(7));
  assert.deepEqual(new Set(c.localValue), new Set([7, 8]));
  const received = individual(19);
  assert.equal(received.noAuth, true);
  c.handleSetCurBiz(received);
  assert.equal(c.localCurrentSpace, null);
  c.searchValue = 'pin';
  const search = c.loadDirectory();
  h.normal[2].resolve({ items: [space(22, '拼音')], next_cursor: null });
  h.alerts[1].resolve({ items: [], next_cursor: null });
  await search;
  assert.deepEqual(c.pagination.data.map(s => s.id), [22]);
  c.handleSelectOption(individual(22));
  assert.deepEqual(new Set(c.localValue), new Set([7, 8, 22]));
});

test('Vue2 resolves historical IDs through VIEW first, and only asks the alert service about missing IDs', async () => {
  const h = setup(), c = component('monitor-pc/components/space-select/space-select.tsx', h);
  Object.assign(c, { remote: true, hasAuthApply: true, value: [31, 17], spaceList: [], localValue: [31, 17] });
  const result = c.resolveSelection([31, 17]);
  assert.equal(h.normal[0].params.bk_biz_ids, '31,17');
  h.normal[0].resolve({ items: [space(17)], next_cursor: null });
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(h.alerts[0].params.bk_biz_ids, '31');
  h.alerts[0].resolve({ items: [{ bk_biz_id: 31, bk_biz_name: 'restricted', has_data: false }], next_cursor: null });
  await result;
  assert.equal(c.localSpaceList.find(row => row.id === 17).noAuth, undefined);
  assert.equal(c.localSpaceList.find(row => row.id === 31).noAuth, true);
  const before = [...c.localValue];
  c.handleSelectOption(c.localSpaceList.find(row => row.id === 31));
  assert.deepEqual(c.localValue, before);
});

test('top bar honors remote pinyin matching even when returned rows contain no local pinyin', async () => {
  const h = setup(), c = component('monitor-pc/components/biz-select/biz-select.tsx', h);
  Object.assign(c, { remote: true, bizList: [], commonListIds: [], stickyList: [], showBizList: true, keyword: 'bj', searchTypeId: 'bcs' });
  const result = c.loadDirectory();
  h.normal[0].resolve({ items: [{ ...space(-15, '北京'), space_code: 'project', space_type_id: 'bkci' }], next_cursor: null });
  await result;
  assert.deepEqual(c.keyboardItems.map(row => row.id), [-15]);
});

test('home selector excludes existing tabs after a remote search without filtering server-side pinyin matches', async () => {
  const h = setup(), c = component('monitor-pc/pages/home/new-home/components/home-biz-list.tsx', h);
  Object.assign(c, { remote: true, bizList: [], excludeIds: [12], commonListIds: [], stickyList: [], showBizList: true, keyword: 'bj' });
  const result = c.loadDirectory();
  h.normal[0].resolve({ items: [space(12, '北京'), space(77, '北郊')], next_cursor: null });
  await result;
  assert.deepEqual(c.bizListFilter.flatMap(group => group.children.map(row => row.id)), [77]);
});


