const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const ts = require('typescript');

const viewRoot = path.join(__dirname, '../src/monitor-pc/pages/strategy-config/strategy-config-set/strategy-view');

function loadMethods(file, names, dependencies) {
  const source = ts.createSourceFile(file, fs.readFileSync(file, 'utf8'), ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  const component = source.statements.find(ts.isClassDeclaration);
  const methods = names.map(name => {
    const method = component.members.find(member => member.name?.getText(source) === name);
    assert.ok(method, `Missing ${name}`);
    return method.getText(source);
  });
  const code = ts.transpileModule(`class Harness { ${methods.join('\n')} } return Harness.prototype;`, {
    compilerOptions: { target: ts.ScriptTarget.ES2022 },
  }).outputText;
  return new Function(...Object.keys(dependencies), code)(...Object.values(dependencies));
}

const chartMethods = loadMethods(path.join(viewRoot, 'strategy-chart/strategy-chart.tsx'),
  ['getQueryParams', 'getExpression', 'createMetrics'], {
    LETTERS: ['a', 'b', 'c', 'd'],
    CustomEventMetricAll: '__all__',
    EShortcutsType: { NEAR: 'near' },
    typeTools: { isNull: value => value == null },
  });

function harness({ intelligent = false, forecast = false, near = false, mounted = true } = {}) {
  const metrics = [
    { alias: 'a', agg_dimension: ['bk_target_ip', 'bk_target_cloud_id'] },
    { alias: 'b', agg_dimension: ['bk_host_id', 'bk_target_ip'] },
  ].map(metric => ({
    data_source_label: 'custom', data_type_label: 'event', metricMetaId: 'custom|event',
    result_table_id: 'test_event', metric_field: 'event.count', agg_method: 'SUM', agg_interval: 60,
    agg_condition: [{ key: 'status', method: 'eq', value: ['active'] }, { key: '', value: [] }],
    extend_fields: {}, keywords_query_string: 'disk', custom_event_name: 'disk_event',
    intelligent_detect: { agg_dimension: ['service_instance_id'], agg_condition: [], result_table_id: 'test_detect' },
    ...metric,
  }));
  const chart = Object.assign(Object.create(chartMethods), {
    metricData: metrics, hasIntelligentDetect: intelligent, hasTimeSeriesForecast: forecast,
    intelligentDetect: metrics[0].intelligent_detect, aiopsChartType: 'none',
    editMode: 'Edit', expression: '', detectionConfig: { data: [] }, dimensions: {},
    shortcutsType: 'custom', strategyTarget: [],
  });
  const calls = [];
  const viewMethods = loadMethods(path.join(viewRoot, 'strategy-view.tsx'), ['handleLogQuery'], {
    handleTransformToTimestamp: () => [100, 200],
    logQuery: async params => { calls.push(params); return { data: [], meta: { total: 0 } }; },
  });
  const view = Object.assign(Object.create(viewMethods), {
    metricQueryData: metrics, metricData: metrics, strategyChartRef: mounted ? chart : undefined,
    strategyTarget: [[{ field: 'host_topo_node', value: [{ bk_obj_id: 'module', bk_inst_id: 10 }] }]],
    tools: { timeRange: [100, 200] }, isNear: near, isAlertStrategy: false,
    dimensions: { device: 'disk-a' }, limit: 20,
    getQueryParams: () => chart.getQueryParams(),
  });
  return { view, chart, calls };
}

test('log request reuses the multi-metric curve target dimensions and existing conditions', async () => {
  const { view, calls } = harness();
  await view.handleLogQuery();
  assert.deepEqual(calls[0].target, view.strategyTarget);
  assert.deepEqual(calls[0].group_by, ['bk_target_ip', 'bk_target_cloud_id', 'bk_host_id']);
  assert.deepEqual(calls[0].where, [{ key: 'status', method: 'eq', value: ['active'] }]);
  assert.deepEqual(calls[0].filter_dict, { device: 'disk-a', event_name: 'disk_event' });
  assert.equal(calls[0].query_string, 'disk');
  assert.equal(calls[0].limit, 20);
});

for (const mode of ['intelligent', 'forecast']) {
  test(`${mode} logs use the actual curve dimension override`, async () => {
    const { view, chart, calls } = harness({ [mode]: true });
    await view.handleLogQuery();
    const curve = chart.getQueryParams(true);
    assert.deepEqual(calls[0].group_by, [...new Set(curve.query_configs.flatMap(item => item.group_by))]);
    assert.deepEqual(calls[0].group_by, ['service_instance_id']);
  });
}

test('near mode, subsequent loads and target changes retain the current target', async () => {
  const { view, calls } = harness({ near: true });
  await view.handleLogQuery();
  assert.deepEqual(calls[0].filter_dict, { event_name: 'disk_event' });
  view.strategyTarget = [[{ field: 'host_topo_node', value: [{ bk_obj_id: 'module', bk_inst_id: 20 }] }]];
  view.limit = 40;
  await view.handleLogQuery();
  assert.deepEqual(calls[1].target, view.strategyTarget);
  assert.equal(calls[1].limit, 40);
  view.strategyTarget = undefined;
  await view.handleLogQuery();
  assert.deepEqual(calls[2].target, []);
});

test('legacy preview path uses its existing query builder before the chart mounts', async () => {
  const { view, calls } = harness({ mounted: false });
  await view.handleLogQuery();
  assert.deepEqual(calls[0].group_by, ['bk_target_ip', 'bk_target_cloud_id', 'bk_host_id']);
  assert.deepEqual(calls[0].target, view.strategyTarget);
});
