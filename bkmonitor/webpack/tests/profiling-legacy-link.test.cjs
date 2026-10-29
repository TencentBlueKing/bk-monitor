const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const ts = require('typescript');

function load(file) {
  const { outputText, diagnostics } = ts.transpileModule(
    fs.readFileSync(path.join(__dirname, '../src', file), 'utf8'),
    {
      compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
      reportDiagnostics: true,
    }
  );
  assert.equal(diagnostics.length, 0);
  const module = { exports: {} };
  new Function('module', 'exports', 'window', outputText)(module, module.exports, {
    i18n: { t: value => value },
  });
  return module.exports;
}

const { buildProfilingExploreLocation } = load('monitor-common/utils/profiling-url.ts');
const { restoreQueryState, buildFileQuery, buildProfileQuery } = load('trace/pages/profiling-explore/utils/query.ts');
const { EMethod, METHOD_MAP } = load('trace/components/retrieval-filter/typing.ts');
const { COMMON_ROUTE_LIST, getRouteConfig, normalizeStoredRouteIds } = load('monitor-pc/router/router-config.ts');
const range = [1700000000000, 1700000060000];

function restoreLegacy(target) {
  const location = buildProfilingExploreLocation(encodeURIComponent(JSON.stringify(target)));
  assert.equal(location.path, '/trace/profiling-explore');
  return restoreQueryState(JSON.parse(location.query.profiling), 'UTC');
}

for (const [legacyMode, graphMode] of [['flame', 'flame'], ['table', 'table'], ['topo', 'callgraph']]) {
  test(`legacy file ${legacyMode} restores the file view without changing the application view`, () => {
    const state = restoreLegacy({ profile_id: 'test-profile', diagram_types: [legacyMode] });
    assert.equal(state.view.tab, 'file');
    assert.equal(state.file.view.graphMode, graphMode);
    assert.equal(state.view.graphMode, 'combined');
    assert.equal(state.file.profileId, 'test-profile');
    assert.equal(state.file.pendingTimeRange, true);
  });
}

test('legacy application and comparison labels use the UI equality operator and retain request values', () => {
  const state = restoreLegacy({
    app_name: 'test-app',
    service_name: 'test-service',
    filter_labels: { instance: ['worker-a', 'worker-b'] },
    diff_filter_labels: { instance: 'worker-c' },
    is_compared: true,
    diagram_types: ['topo'],
  });
  for (const item of [...state.where, ...state.comparisonWhere]) {
    assert.equal(item.method, EMethod.eq);
    assert.equal(METHOD_MAP[item.method], '=');
  }
  const query = buildProfileQuery(state, 1, range);
  assert.deepEqual(query.filter_labels, { instance: ['worker-a', 'worker-b'] });
  assert.deepEqual(query.diff_filter_labels, { instance: 'worker-c' });
  assert.equal(query.is_compared, true);
  assert.equal(state.view.graphMode, 'combined');
});

test('legacy file labels retain the same request values with the UI equality operator', () => {
  const state = restoreLegacy({ profile_id: 'test-profile', filter_labels: { instance: 'worker-a' } });
  assert.equal(state.file.where[0].method, EMethod.eq);
  assert.equal(METHOD_MAP[state.file.where[0].method], '=');
  const query = buildFileQuery(state, 1, range);
  assert.equal(query.profile_id, 'test-profile');
  assert.deepEqual(query.filter_labels, { instance: 'worker-a' });
});

for (const isCompared of [false, 0, 'false']) {
  test(`legacy links with is_compared=${JSON.stringify(isCompared)} keep comparison disabled despite saved labels`, () => {
    const state = restoreLegacy({
      app_name: 'test-app',
      service_name: 'test-service',
      is_compared: isCompared,
      filter_labels: { instance: 'worker-a' },
      diff_filter_labels: { instance: 'worker-b' },
      diagram_types: ['callgraph'],
    });
    const query = buildProfileQuery(state, 1, range);
    assert.equal(state.mode, 'none');
    assert.equal(state.view.graphMode, 'callgraph');
    assert.equal(query.is_compared, false);
    assert.deepEqual(query.filter_labels, { instance: 'worker-a' });
    assert.deepEqual(query.diff_filter_labels, {});
  });
}

test('legacy links without a comparison flag still infer comparison from labels', () => {
  const state = restoreLegacy({
    app_name: 'test-app',
    service_name: 'test-service',
    diff_filter_labels: { instance: 'worker-b' },
    diagram_types: ['callgraph'],
  });
  const query = buildProfileQuery(state, 1, range);
  assert.equal(state.mode, 'condition');
  assert.equal(state.view.graphMode, 'combined');
  assert.equal(query.is_compared, true);
  assert.deepEqual(query.diff_filter_labels, { instance: 'worker-b' });
});

test('legacy time comparison retains both selections and their request bounds', () => {
  const midpoint = (range[0] + range[1]) / 2;
  const state = restoreLegacy({
    app_name: 'test-app',
    service_name: 'test-service',
    is_compared: true,
    filter_labels: { start: range[0] * 1000, end: midpoint * 1000 },
    diff_filter_labels: { start: midpoint * 1000, end: range[1] * 1000 },
  });
  const query = buildProfileQuery(state, 1, range);
  assert.equal(state.mode, 'time');
  assert.equal(query.is_compared, true);
  assert.deepEqual(query.filter_labels, { start: range[0] * 1000, end: midpoint * 1000 });
  assert.deepEqual(query.diff_filter_labels, { start: midpoint * 1000, end: range[1] * 1000 });
});

test('common navigation exposes only the new Profiling entry while retaining legacy route metadata', () => {
  const entries = COMMON_ROUTE_LIST.flatMap(item => item.children || [item]);
  assert.deepEqual(entries.filter(item => item.name === 'Profiling 检索').map(item => item.id), ['profiling-explore']);
  assert.equal(entries.find(item => item.id === 'profiling-explore').canStore, true);
  const legacy = getRouteConfig().flatMap(item => item.children || [item]).find(item => item.id === 'profiling');
  assert.equal(legacy.path, '/trace/profiling');
  assert.equal(legacy.hidden, true);
});

test('mixed old and new favorites normalize once without changing unrelated entries or order', () => {
  assert.deepEqual(
    normalizeStoredRouteIds(['profiling', 'collect-config', 'profiling-explore', 'performance', 'host', 'profiling']),
    ['profiling-explore', 'collect-config', 'host']
  );
  assert.deepEqual(normalizeStoredRouteIds(['profiling-explore', 'profiling']), ['profiling-explore']);
});
