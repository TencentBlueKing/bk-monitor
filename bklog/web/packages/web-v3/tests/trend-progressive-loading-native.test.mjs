import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import ts from 'typescript';

const deferred = () => {
  let resolve, reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
};
const flush = async () => { for (let i = 0; i < 8; i++) await Promise.resolve(); };
const response = count => ({ result: true, data: { aggs: { group_by_histogram: { buckets: Array.from({ length: count }, (_, key) => ({ key, doc_count: key + 1 })) } } } });

function fixture({ segmented = true, worker = false } = {}) {
  const source = readFileSync(new URL('../src/features/retrieval/workbench/search-result-chart/index.tsx', import.meta.url), 'utf8');
  const start = source.indexOf('    const getSeriesData = async');
  const end = source.indexOf('    // 趋势图数据请求生成器', start);
  const pending = [deferred(), deferred(), deferred()];
  const workerResult = deferred();
  let current = 1, status = 'loading', requested = 0;
  const events = [];
  const context = {
    setTrendStatus: value => { status = value; events.push(['status', value]); },
    markTrendReady: () => events.push(['visible']),
    handleRequestSplit: () => segmented ? 1 : 0,
    getGenFn: function* () {
      for (let i = 0; i < (segmented ? 3 : 1); i++) yield { urlStr: 'synthetic-operation', indexId: '900101', queryData: {}, isInit: i === 0 };
    },
    isCurrentTrendLoad: seq => seq === current,
    logChartCancel: () => events.push(['cancel']),
    fetchTrendChartData: () => pending[requested++].promise,
    processChartDataWithWorker: worker ? async () => { await workerResult.promise; events.push(['worker-processed']); } : undefined,
    setChartData: (data, field, init) => events.push(['paint', data, init]),
    gradeOptions: { value: undefined }, runningInterval: 'auto', store: { indexItem: { timezone: 'UTC' } },
  };
  const js = ts.transpileModule(source.slice(start, end), { compilerOptions: { target: ts.ScriptTarget.ES2022 } }).outputText;
  const run = new Function(...Object.keys(context), js + '\nreturn getSeriesData;')(...Object.values(context));
  return { pending, workerResult, events, run, invalidate: () => { current++; status = 'loading'; }, status: () => status, requested: () => requested };
}

test('single response stays in initial loading until data is painted, then settles without progressive loading', async () => {
  const f = fixture({ segmented: false });
  const job = f.run(0, 1, 1);
  assert.equal(f.status(), 'loading');
  f.pending[0].resolve(response(1));
  await job;
  assert.equal(f.requested(), 1);
  assert.deepEqual(f.events.map(e => e[0]), ['paint', 'visible', 'status']);
  assert.equal(f.status(), 'ready');
});

test('segmented responses reveal the first chunk and append subsequent chunks while showing corner progress', async () => {
  const f = fixture();
  const job = f.run(0, 3, 1);
  assert.equal(f.status(), 'loading');
  f.pending[0].resolve(response(1));
  await flush();
  assert.equal(f.status(), 'polling');
  assert.deepEqual(f.events.map(e => e[0]), ['paint', 'status', 'visible']);
  assert.equal(f.requested(), 2);
  f.pending[1].resolve(response(2));
  await flush();
  assert.equal(f.status(), 'polling');
  assert.equal(f.events.filter(e => e[0] === 'paint').length, 2);
  f.pending[2].resolve(response(3));
  await job;
  assert.deepEqual(f.events.filter(e => e[0] === 'paint').map(e => e[2]), [true, false, false]);
  assert.equal(f.events.filter(e => e[0] === 'visible').length, 1);
  assert.equal(f.status(), 'ready');
});

test('initial skeleton waits for worker processing; worker failure falls back before revealing the chart', async () => {
  for (const fail of [false, true]) {
    const f = fixture({ worker: true });
    const job = f.run(0, 3, 1);
    f.pending[0].resolve(response(101));
    await flush();
    assert.equal(f.status(), 'loading');
    assert.equal(f.events.length, 0);
    if (fail) f.workerResult.reject(new Error('synthetic-worker-error'));
    else f.workerResult.resolve();
    await flush();
    assert.equal(f.status(), 'polling');
    assert.equal(f.events[0][0], fail ? 'paint' : 'worker-processed');
    assert.equal(f.events.filter(e => e[0] === 'paint').length, 1);
    f.pending[1].resolve(response(1)); f.pending[2].resolve(response(1));
    await job;
    assert.equal(f.status(), 'ready');
  }
});

test('stale first or subsequent chunk cannot reveal, paint or settle a replacement query', async () => {
  for (const afterFirst of [false, true]) {
    const f = fixture();
    const job = f.run(0, 3, 1);
    if (afterFirst) { f.pending[0].resolve(response(1)); await flush(); }
    f.invalidate();
    const before = f.events.length;
    f.pending[afterFirst ? 1 : 0].resolve(response(2));
    await job;
    assert.equal(f.events.length, before);
    assert.equal(f.status(), 'loading');
  }
});

test('first and subsequent failures settle loading and retain the existing chart-clear behavior', async () => {
  for (const afterFirst of [false, true]) {
    const f = fixture();
    const job = f.run(0, 3, 1);
    if (afterFirst) { f.pending[0].resolve(response(1)); await flush(); }
    f.pending[afterFirst ? 1 : 0].reject(new Error('synthetic-request-error'));
    await job;
    assert.equal(f.status(), 'ready');
    assert.deepEqual(f.events.filter(e => e[0] === 'paint').at(-1), ['paint', null, true]);
    assert.equal(f.events.filter(e => e[0] === 'visible').length, 1);
  }
});

test('worker completion from an invalidated query cannot commit data or release the new skeleton', async () => {
  const f = fixture({ worker: true });
  const job = f.run(0, 3, 1);
  f.pending[0].resolve(response(101));
  await flush();
  f.invalidate();
  f.workerResult.resolve();
  await job;
  assert.equal(f.status(), 'loading');
  assert.equal(f.events.some(e => e[0] === 'paint' || e[0] === 'visible' || e[0] === 'status'), false);
});
