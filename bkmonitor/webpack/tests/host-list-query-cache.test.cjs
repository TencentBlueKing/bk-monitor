const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const ts = require('typescript');

const source = fs.readFileSync(path.join(__dirname, '../src/trace/pages/host/services/host-service.ts'), 'utf8');
const code = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText;
const flush = () => new Promise(resolve => setImmediate(resolve));

function harness() {
  let now = 0;
  let anchorCalls = 0;
  let nextTimer = 0;
  const timers = new Map();
  const calls = [];
  const owner = {
    setTimeout: (callback, delay) => {
      timers.set(++nextTimer, { callback, due: now + delay });
      return nextTimer;
    },
    clearTimeout: id => timers.delete(id),
  };
  const services = Object.fromEntries(['getHostInfoList', 'getHostMetricInfoList'].map(name => [name, params =>
    new Promise((resolve, reject) => calls.push({ name, params, resolve, reject }))
  ]));
  const load = () => {
    const module = { exports: {} };
    new Function('require', 'module', 'exports', 'window', 'Date', code)(
      id => {
        if (id === 'monitor-api/base') return { request: () => () => {} };
        if (id === 'monitor-api/modules/commons') return {};
        assert.equal(id, 'monitor-api/modules/performance');
        return { searchHostInfo: services.getHostInfoList, searchHostMetric: services.getHostMetricInfoList };
      }, module, module.exports, { rawWindow: owner }, { now: () => now }
    );
    return module.exports;
  };
  const api = load();
  const getTimeParams = () => {
    anchorCalls += 1;
    return { start_time: now / 1000 - 3600, end_time: now / 1000 };
  };
  const get = (key = 'query-a', force = false, scope = {}, module = api) =>
    module.getHostListQuery(key, scope, getTimeParams, force);
  const setTime = value => {
    now = value;
    for (const [id, timer] of timers) {
      if (timer.due > now) continue;
      timers.delete(id);
      timer.callback();
    }
  };
  return { api, calls, get, load, owner, timers, setTime, anchorCalls: () => anchorCalls };
}

test('pending and resolved queries survive module recreation without moving the time anchor', async () => {
  const h = harness();
  const first = h.get();
  h.setTime(10_000);
  assert.equal(h.get('query-a', false, {}, h.load()), first);
  assert.equal(h.calls.length, 2);
  assert.equal(h.anchorCalls(), 1);
  assert.equal(first.timeParams.end_time, 0);
  h.calls[0].resolve([]);
  h.calls[1].resolve({});
  await flush();
  assert.equal(first.resolved, true);
  h.setTime(59_999);
  assert.equal(h.get(), first);
  assert.equal(first.expiresAt, 60_000);
});

test('expiry is measured from start, is not renewed by hits, and releases the cache without another visit', () => {
  const h = harness();
  h.get();
  h.setTime(30_000);
  h.get();
  h.setTime(60_000);
  assert.equal(h.owner.__MONITOR_HOST_LIST_QUERY__, undefined);
  assert.equal(h.timers.size, 0);
  const next = h.get();
  assert.equal(next.timeParams.end_time, 60);
  assert.equal(h.calls.length, 4);
});

test('elapsed TTL prevents reuse even when an inactive-tab timer has not fired', () => {
  const h = harness();
  const first = h.get();
  first.expiresAt = -1;
  assert.notEqual(h.get(), first);
  assert.equal(h.calls.length, 4);
  assert.equal(h.timers.size, 1);
});

test('different context and force refresh each replace the single entry and cancel its timer', () => {
  const h = harness();
  const first = h.get();
  h.setTime(1000);
  const other = h.get('query-b');
  assert.notEqual(other, first);
  assert.equal(h.timers.size, 1);
  h.setTime(2000);
  const forced = h.get('query-b', true);
  assert.notEqual(forced, other);
  assert.equal(forced.timeParams.end_time, 2);
  assert.equal(h.calls.length, 6);
  assert.equal(h.timers.size, 1);
});

test('late failure, Worker invalidation and expiry cannot clear a newer same-key refresh', async () => {
  const h = harness();
  const first = h.get();
  const oldExpiry = h.timers.get(first.timer).callback;
  const refreshed = h.get('query-a', true);
  h.calls[0].reject(new Error('old HTTP failure'));
  await flush();
  h.api.clearHostListQueryCache(first);
  oldExpiry();
  assert.equal(h.owner.__MONITOR_HOST_LIST_QUERY__, refreshed);
  assert.equal(h.timers.size, 1);
});

test('failure evicts pending state even with no mounted consumer', async () => {
  const h = harness();
  h.get();
  h.calls[1].reject(new Error('metrics failed'));
  await flush();
  assert.equal(h.owner.__MONITOR_HOST_LIST_QUERY__, undefined);
  assert.equal(h.timers.size, 0);
  h.get();
  assert.equal(h.calls.length, 4);
});

test('uncacheable identity and explicit host or topology scopes keep the original request contract', () => {
  const h = harness();
  assert.equal(h.get(null), null);
  assert.equal(h.get('', false), null);
  assert.equal(h.get('shared-host', false, { bk_host_id: 1 }), null);
  assert.equal(h.get('shared-topo', false, { bk_obj_id: 'module', bk_inst_id: 2 }), null);
  assert.equal(h.calls.length, 0);
  assert.equal(h.timers.size, 0);
});
