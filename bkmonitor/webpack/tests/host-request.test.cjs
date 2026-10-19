const assert = require('node:assert/strict');
const test = require('node:test');

const vue = require('../src/trace/node_modules/vue');
const { loadHostModule, serviceHarness, flush } = require('./helpers/host-service-harness.cjs');

const cases = [
  ['getHostOrTopoNodeDetail', [{ bk_biz_id: 1, bk_host_id: 11 }]],
  ['getHostInfoList', [{}]],
  ['getHostInfoPage', [{ page: 1, page_size: 50 }]],
  ['getHostMetricStats', [{ category: 'cpu', start_time: 100, end_time: 200 }]],
  ['getHostMetricInfoList', [{ start_time: 100, end_time: 200 }]],
  ['getHostTopoTreeByBizId', [1, {}, false]],
  ['getHostViewsPanelsApi', []],
  ['getHostMetricGroupPanelOrderApi', []],
  ['getProcessViewsPanelsApi', []],
  ['getProcessMetricGroupPanelOrderApi', []],
  ['getHostProcessList', [{ bk_host_id: 11, start_time: 100, end_time: 200 }]],
  ['getHostProcessUptime', [{ bk_biz_id: 1, bk_host_id: 11, display_name: 'nginx', start_time: 100, end_time: 200 }]],
  ['getStrategyAndEventCountApi', [{ scene_id: 'host', target: { bk_host_id: 11 } }]],
];

for (const [name, args] of cases) {
  test(`${name} shares pending work across module recreation, then requests again after success`, async () => {
    const first = serviceHarness();
    const original = first.api[name](...args);
    const second = serviceHarness(first.owner);
    assert.equal(second.api[name](...args), original);
    await flush();
    assert.equal(first.calls.length, 1);
    assert.equal(second.calls.length, 0);
    first.calls[0].resolve([]);
    assert.deepEqual(await original, []);
    assert.equal(first.owner.__MONITOR_HOST_PENDING_REQUESTS__.size, 0);
    const next = second.api[name](...args);
    assert.notEqual(next, original);
    await flush();
    assert.equal(second.calls.length, 1);
    second.calls[0].resolve([]);
    await next;
  });
}

test('failure and synchronous exceptions release the entry without retaining rejected promises', async () => {
  const h = serviceHarness();
  const error = new Error('timeout');
  const first = h.api.getHostInfoList();
  const observed = assert.rejects(first, error);
  await flush();
  h.calls[0].reject(error);
  await observed;
  assert.equal(h.owner.__MONITOR_HOST_PENDING_REQUESTS__.size, 0);
  const second = h.api.getHostInfoList();
  await flush();
  assert.equal(h.calls.length, 2);
  h.calls[1].resolve([]);
  await second;
  await assert.rejects(
    h.requestHost('throw', {}, () => {
      throw error;
    }),
    error
  );
  assert.equal(h.owner.__MONITOR_HOST_PENDING_REQUESTS__.size, 0);
});

test('canonical parameters ignore object key order, snapshot input, and include implicit business', async () => {
  const h = serviceHarness();
  const params = { target: { b: 2, a: 1 }, scene_id: 'host' };
  const first = h.api.getStrategyAndEventCountApi(params);
  assert.equal(first, h.api.getStrategyAndEventCountApi({ bk_biz_id: 1, scene_id: 'host', target: { a: 1, b: 2 } }));
  params.target.a = 99;
  await flush();
  assert.equal(h.calls.length, 1);
  assert.deepEqual(h.calls[0].params.target, { a: 1, b: 2 });
  assert.equal(h.calls[0].params.bk_biz_id, 1);
  assert.equal('bk_biz_id' in params, false);
  h.calls[0].resolve({});
  await first;
});

test('different scopes, pages, topology modes, metrics and times run independently', async () => {
  const h = serviceHarness();
  const promises = [
    h.api.getHostInfoList(),
    h.api.getHostInfoList({ bk_biz_id: 2 }),
    h.api.getHostInfoList({ bk_host_id: 1 }),
    h.api.getHostInfoPage({ page: 1, page_size: 50 }),
    h.api.getHostInfoPage({ page: 2, page_size: 50 }),
    h.api.getHostTopoTreeByBizId(1, {}, false),
    h.api.getHostTopoTreeByBizId(1, {}, true),
    h.api.getHostMetricInfoList({ start_time: 100, end_time: 200 }),
    h.api.getHostMetricInfoList({ start_time: 101, end_time: 201 }),
    h.api.getHostMetricInfoList({ start_time: 100, end_time: 200, bk_host_ids: [1, 2] }),
    h.api.getHostMetricInfoList({ start_time: 100, end_time: 200, bk_host_ids: [2, 1] }),
    h.api.getHostMetricStats({ start_time: 100, end_time: 200, category: 'cpu' }),
    h.api.getHostMetricStats({ start_time: 100, end_time: 200, category: 'mem' }),
  ];
  await flush();
  assert.equal(h.calls.length, promises.length);
  h.calls.forEach(call => call.resolve([]));
  await Promise.all(promises);
});

for (const [name, params] of [
  ['getHostMetricStats', { category: 'cpu' }],
  ['getHostMetricInfoList', { bk_host_ids: [11, 12] }],
  ['getHostProcessList', { bk_host_id: 11 }],
  ['getHostProcessUptime', { bk_biz_id: 1, bk_host_id: 11, display_name: 'nginx' }],
]) {
  test(`${name} shares the same relative range across different timestamps without changing the API payload`, async () => {
    const first = serviceHarness();
    const timeContext = { timeRange: ['now-1h', 'now'], timezone: 'UTC' };
    const originalParams = { ...params, start_time: 100, end_time: 3700 };
    const original = first.api[name](originalParams, timeContext);
    const second = serviceHarness(first.owner);
    const nextParams = { ...params, start_time: 110, end_time: 3710 };
    assert.equal(second.api[name](nextParams, { ...timeContext, timeRange: [...timeContext.timeRange] }), original);
    assert.equal(second.calls.length, 0);
    assert.deepEqual(first.calls[0].params, { ...originalParams, bk_biz_id: 1 });
    assert.deepEqual(originalParams, { ...params, start_time: 100, end_time: 3700 });
    first.calls[0].resolve([]);
    await original;
    const next = second.api[name](nextParams, timeContext);
    assert.notEqual(next, original);
    assert.deepEqual(second.calls[0].params, { ...nextParams, bk_biz_id: 1 });
    second.calls[0].resolve([]);
    await next;
  });
}

test('relative expressions, timezone, fixed timestamps and other parameters remain separate', async () => {
  const h = serviceHarness();
  const params = { bk_host_ids: [11], start_time: 100, end_time: 3700 };
  const context = { timeRange: ['now-1h', 'now'], timezone: 'UTC' };
  const promises = [
    h.api.getHostMetricInfoList(params, context),
    h.api.getHostMetricInfoList(params, { ...context, timeRange: ['now-24h', 'now'] }),
    h.api.getHostMetricInfoList(params, { ...context, timezone: 'Asia/Shanghai' }),
    h.api.getHostMetricInfoList(params, { ...context, timeRange: [100, 3700] }),
    h.api.getHostMetricInfoList({ ...params, start_time: 110, end_time: 3710 }, { ...context, timeRange: [100, 3700] }),
    h.api.getHostMetricInfoList(params),
    h.api.getHostMetricInfoList({ ...params, bk_host_ids: [12] }, context),
    h.api.getHostMetricInfoList({ ...params, bk_biz_id: 2 }, context),
  ];
  assert.equal(h.calls.length, promises.length);
  h.calls.forEach(call => call.resolve({}));
  await Promise.all(promises);
});

test('mixed ranges normalize only the relative endpoint and rounded expressions can also share', async () => {
  const h = serviceHarness();
  const read = (start, end, timeRange) =>
    h.api.getHostMetricInfoList({ start_time: start, end_time: end }, { timeRange, timezone: 'UTC' });
  const fixedStart = read(100, 200, [100, 'now']);
  assert.equal(read(100, 210, [100, 'now']), fixedStart);
  const changedStart = read(101, 210, [101, 'now']);
  assert.notEqual(changedStart, fixedStart);
  const fixedEnd = read(100, 200, ['now-1h', 200]);
  assert.equal(read(110, 200, ['now-1h', 200]), fixedEnd);
  const changedEnd = read(110, 201, ['now-1h', 201]);
  assert.notEqual(changedEnd, fixedEnd);
  const rounded = read(100, 200, ['now/d', 'now/d']);
  assert.equal(read(300, 400, ['now/d', 'now/d']), rounded);
  assert.equal(h.calls.length, 5);
  h.calls.forEach(call => call.resolve({}));
  await Promise.all([fixedStart, changedStart, fixedEnd, changedEnd, rounded]);
});

test('relative request keys survive context mutation and failures allow a fresh timestamp', async () => {
  const h = serviceHarness();
  const context = { timeRange: ['now-1h', 'now'], timezone: 'UTC' };
  const first = h.api.getHostMetricInfoList({ start_time: 100, end_time: 3700 }, context);
  context.timeRange[0] = 'now-24h';
  const hour = { timeRange: ['now-1h', 'now'], timezone: 'UTC' };
  assert.equal(h.api.getHostMetricInfoList({ start_time: 110, end_time: 3710 }, hour), first);
  const rejected = assert.rejects(first, /failed/);
  h.calls[0].reject(new Error('failed'));
  await rejected;
  assert.equal(h.owner.__MONITOR_HOST_PENDING_REQUESTS__.size, 0);
  const next = h.api.getHostMetricInfoList({ start_time: 120, end_time: 3720 }, hour);
  assert.equal(h.calls[1].params.end_time, 3720);
  h.calls[1].resolve({});
  await next;
});

test('user, site, backend, share authorization and source contexts are isolated', async () => {
  const first = serviceHarness();
  const all = [
    first,
    ...[
      { user_name: 'another-user' },
      { site_url: '/other/' },
      { cc_biz_id: 2 },
      { __BK_WEWEB_DATA__: { host: 'other-backend' } },
      { token: 'test-share-a' },
      { token: 'test-share-b' },
      { source_app: 'other-source' },
    ].map(context => serviceHarness(first.owner, context)),
  ];
  const promises = all.map(h => h.api.getHostViewsPanelsApi());
  await flush();
  all.forEach(h => {
    assert.equal(h.calls.length, 1);
    h.calls[0].resolve([]);
  });
  await Promise.all(promises);
});

test('business A to B to A reuses A while still pending and standalone mode also shares', async () => {
  const h = serviceHarness({}, { rawWindow: null });
  const first = h.api.getHostViewsPanelsApi();
  h.window.cc_biz_id = 2;
  const second = h.api.getHostViewsPanelsApi();
  h.window.cc_biz_id = 1;
  assert.equal(h.api.getHostViewsPanelsApi(), first);
  await flush();
  assert.equal(h.calls.length, 2);
  h.calls.forEach(call => call.resolve([]));
  await Promise.all([first, second]);
  assert.equal(h.window.__MONITOR_HOST_PENDING_REQUESTS__.size, 0);
});

for (const fails of [false, true]) {
  test(`post-save reads wait for old work, coalesce and do not overlap (${fails ? 'failure' : 'success'})`, async () => {
    const h = serviceHarness();
    const old = h.api.getHostMetricGroupPanelOrderApi();
    const observed = old.catch(() => []);
    const fresh = h.api.getHostMetricGroupPanelOrderApi(true);
    const other = serviceHarness(h.owner);
    assert.equal(other.api.getHostMetricGroupPanelOrderApi(true), fresh);
    assert.equal(other.api.getHostMetricGroupPanelOrderApi(), old);
    await flush();
    assert.equal(h.calls.length, 1);
    h.calls[0][fails ? 'reject' : 'resolve'](fails ? new Error('old failed') : ['old']);
    await observed;
    await flush();
    assert.equal(h.calls.length, 2);
    assert.equal(other.calls.length, 0);
    assert.equal(h.owner.__MONITOR_HOST_PENDING_REQUESTS__.size, 1);
    const concurrent = other.api.getHostMetricGroupPanelOrderApi();
    h.calls[1].resolve(['new']);
    assert.deepEqual(await fresh, ['new']);
    assert.deepEqual(await concurrent, ['new']);
    assert.equal(h.owner.__MONITOR_HOST_PENDING_REQUESTS__.size, 0);
  });
}

test('space UID fallback is part of the effective request and key', async () => {
  const h = serviceHarness({}, { cc_biz_id: -1, space_uid: 'space-a' });
  const first = h.api.getHostViewsPanelsApi();
  h.window.space_uid = 'space-b';
  const second = h.api.getHostViewsPanelsApi();
  await flush();
  assert.deepEqual(
    h.calls.map(call => call.params),
    [{ space_uid: 'space-a' }, { space_uid: 'space-b' }]
  );
  h.calls.forEach(call => call.resolve([]));
  await Promise.all([first, second]);
});

function detailPage(h, target) {
  const node = vue.shallowRef(target);
  const timers = [];
  const refreshGeneration = vue.shallowRef(0);
  const { useHostDetail } = loadHostModule('composables/use-host-detail.ts', {
    vue: { ...vue, provide() {} },
    '@vueuse/core': {
      useDebounceFn:
        fn =>
        (...args) =>
          timers.push(() => fn(...args)),
    },
    pinia: { storeToRefs: value => value },
    '@/store/modules/host': { useHostStore: () => ({ refreshGeneration }) },
    '../utils/topo-tree': { isHostNode: value => 'bk_host_id' in value },
    'monitor-api/modules/scene_view': h.sceneView,
    '../services/host-service': h.api,
  });
  const effect = vue.effectScope();
  const data = effect.run(() => useHostDetail(node));
  return { effect, data, node, send: () => timers.shift()() };
}

for (const target of [
  { bk_biz_id: 1, bk_host_id: 11 },
  { bk_biz_id: 1, bk_obj_id: 'biz', bk_inst_id: 1 },
]) {
  test(`detail remount keeps one in-flight API call for ${'bk_host_id' in target ? 'host' : 'topology'} selection`, async () => {
    const first = serviceHarness();
    const oldPage = detailPage(first, target);
    const oldFetch = oldPage.send();
    assert.equal(first.calls.length, 1);
    oldPage.effect.stop();
    const second = serviceHarness(first.owner);
    const newPage = detailPage(second, { ...target });
    const newFetch = newPage.send();
    assert.equal(second.calls.length, 0, 'returning before completion must reuse the original HTTP request');
    first.calls[0].resolve([{ label: 'Name', type: 'string', value: 'example' }]);
    await Promise.all([oldFetch, newFetch]);
    assert.deepEqual(oldPage.data.detailData.value, []);
    assert.equal(newPage.data.detailData.value[0].value, 'example');
    newPage.effect.stop();
    const afterCompletion = detailPage(second, target);
    const nextFetch = afterCompletion.send();
    assert.equal(second.calls.length, 1, 'completed data must not be cached');
    second.calls[0].resolve([]);
    await nextFetch;
    afterCompletion.effect.stop();
  });
}

test('detail consumers share HTTP but keep independent expansion state', async () => {
  const first = serviceHarness();
  const second = serviceHarness(first.owner);
  const target = { bk_biz_id: 1, bk_host_id: 11 };
  const pageA = detailPage(first, target);
  const pageB = detailPage(second, target);
  const requests = [pageA.send(), pageB.send()];
  const item = Object.freeze({ name: 'IPs', type: 'list', value: ['127.0.0.1'] });
  first.calls[0].resolve(Object.freeze([item]));
  await Promise.all(requests);
  assert.equal(second.calls.length, 0);
  assert.equal(pageA.data.error.value, false);
  assert.equal(pageB.data.error.value, false);
  const rowA = pageA.data.detailData.value[0];
  const rowB = pageB.data.detailData.value[0];
  assert.notEqual(rowA, item);
  assert.notEqual(rowA, rowB);
  rowA.isExpand = true;
  assert.equal(rowB.isExpand, false);
  assert.equal('isExpand' in item, false);
  pageA.effect.stop();
  pageB.effect.stop();
});

test('detail remount observes a pending failure and can retry with a new HTTP request', async () => {
  const first = serviceHarness();
  const target = { bk_biz_id: 1, bk_host_id: 11 };
  const oldPage = detailPage(first, target);
  const oldFetch = oldPage.send();
  oldPage.effect.stop();
  const second = serviceHarness(first.owner);
  const newPage = detailPage(second, target);
  const newFetch = newPage.send();
  first.calls[0].reject(new Error('offline'));
  await Promise.all([oldFetch, newFetch]);
  assert.equal(oldPage.data.error.value, false);
  assert.equal(newPage.data.error.value, true);
  assert.equal(first.owner.__MONITOR_HOST_PENDING_REQUESTS__.size, 0);
  newPage.data.retry();
  const retry = newPage.send();
  assert.equal(second.calls.length, 1);
  second.calls[0].resolve([]);
  await retry;
  assert.equal(newPage.data.error.value, false);
  assert.equal(newPage.data.loading.value, false);
  newPage.effect.stop();
});

test('detail node changes request independently and ignore the previous node response', async () => {
  const h = serviceHarness();
  const page = detailPage(h, { bk_biz_id: 1, bk_host_id: 11 });
  const oldFetch = page.send();
  page.node.value = { bk_biz_id: 1, bk_host_id: 12 };
  const newFetch = page.send();
  assert.deepEqual(
    h.calls.map(call => call.params.bk_host_id),
    [11, 12]
  );
  h.calls[1].resolve([{ name: 'Name', type: 'string', value: 'current' }]);
  await newFetch;
  h.calls[0].resolve([{ name: 'Name', type: 'string', value: 'old' }]);
  await oldFetch;
  assert.equal(page.data.detailData.value[0].value, 'current');
  page.effect.stop();
});

function processPage(h, hostId = 11, anchor = 200) {
  const host = vue.shallowRef({ bk_host_id: hostId, bk_biz_id: 1 });
  const store = {
    timeRangeTimestamp: vue.shallowRef({ start_time: anchor - 100, end_time: anchor }),
    timeRange: vue.shallowRef(['now-1h', 'now']),
    timezone: vue.shallowRef('UTC'),
  };
  const { useProcessList } = loadHostModule('composables/use-process-list.ts', {
    vue,
    pinia: { storeToRefs: value => value },
    '../../../store/modules/host': { useHostStore: () => store },
    '../services/process-service': h.api,
  });
  const effect = vue.effectScope();
  const data = effect.run(() => useProcessList({ host, keyword: vue.shallowRef('') }));
  return { effect, data, host };
}

test('process remount reuses a pending relative range despite timestamp drift and ignores the old response', async () => {
  const first = serviceHarness();
  const oldPage = processPage(first);
  await flush();
  oldPage.effect.stop();
  const second = serviceHarness(first.owner);
  const newPage = processPage(second, 11, 210);
  await flush();
  assert.equal(first.calls.length, 1);
  assert.equal(first.calls[0].config, undefined);
  assert.equal(second.calls.length, 0);
  first.calls[0].resolve([{ name: 'process-a' }]);
  await flush();
  assert.deepEqual(oldPage.data.displayList.value, []);
  assert.deepEqual(newPage.data.displayList.value, [{ name: 'process-a' }]);
  newPage.effect.stop();
});

test('process host switches ignore late responses without cancelling another consumer', async () => {
  const h = serviceHarness();
  const page = processPage(h);
  page.host.value = { bk_host_id: 12, bk_biz_id: 1 };
  await flush();
  assert.equal(h.calls.length, 2);
  h.calls[1].resolve([{ name: 'current' }]);
  await flush();
  h.calls[0].resolve([{ name: 'old' }]);
  await flush();
  assert.deepEqual(page.data.displayList.value, [{ name: 'current' }]);
  page.effect.stop();
});
