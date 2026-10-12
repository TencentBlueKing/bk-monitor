const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const ts = require('typescript');

const dayjs = require('../src/trace/node_modules/dayjs');
const vue = require('../src/trace/node_modules/vue');
const { createRouter, createMemoryHistory } = require('../src/trace/node_modules/vue-router');

dayjs.extend(require('../src/trace/node_modules/dayjs/plugin/utc'));
dayjs.extend(require('../src/trace/node_modules/dayjs/plugin/timezone'));

const root = path.join(__dirname, '../src/trace/pages/profiling-explore');
const lifecycle = { ...vue, onMounted: () => {} };
const i18n = { useI18n: () => ({ t: value => value }) };

function load(file, dependencies = {}) {
  const { outputText, diagnostics } = ts.transpileModule(fs.readFileSync(file, 'utf8'), {
    compilerOptions: {
      module: ts.ModuleKind.CommonJS,
      target: ts.ScriptTarget.ES2022,
      jsx: ts.JsxEmit.React,
      jsxFactory: 'h',
    },
    reportDiagnostics: true,
  });
  assert.equal(diagnostics.length, 0);
  const module = { exports: {} };
  new Function('require', 'module', 'exports', outputText)(
    id => {
      if (id in dependencies) return dependencies[id];
      if (id === 'vue') return lifecycle;
      if (id === 'vue-i18n') return i18n;
      if (id === 'lodash') return require('lodash');
      throw new Error(`Unexpected dependency: ${id}`);
    },
    module,
    module.exports
  );
  return module.exports;
}

test('RetrievalFilter fields/where loads candidates and shares the request across searches', async () => {
  const calls = [];
  const { useProfilingQuery } = load(`${root}/composables/use-profiling-query.ts`, {
    '@blueking/date-picker': {},
    'vue-router': { useRoute: () => ({ query: {} }), useRouter: () => ({}) },
    '../services/profiling': {
      getLabelValues: async (...args) => {
        calls.push(args);
        return ['worker-a', 'Worker-B', 'api'];
      },
    },
    '../utils/query': load(`${root}/utils/query.ts`),
    '@/components/retrieval-filter/typing': {},
    '@/i18n/dayjs': { getDefaultTimezone: () => 'UTC' },
    '@/store/modules/app': { useAppStore: () => ({ bizId: 1 }) },
  });
  const scope = vue.effectScope();
  try {
    const query = scope.run(useProfilingQuery);
    const submitted = { app_name: 'test', service_name: 'worker' };
    query.submitted.value = submitted;
    const [all, filtered] = await Promise.all([
      query.getFieldValues({ fields: ['instance'], where: [], limit: 50 }),
      query.getFieldValues({
        fields: ['instance'],
        where: [{ key: 'instance', method: 'equal', value: ['WORKER'], options: { is_wildcard: true } }],
        limit: 50,
      }),
    ]);
    assert.deepEqual(
      all.list.map(item => item.id),
      ['worker-a', 'Worker-B', 'api']
    );
    assert.deepEqual(
      filtered.list.map(item => item.id),
      ['worker-a', 'Worker-B']
    );
    assert.equal(filtered.count, 2);
    assert.equal(calls.length, 1);
    assert.equal(calls[0][0], submitted);
    assert.equal(calls[0][1], 'instance');
    assert.equal(calls[0][2], 50);
    assert.deepEqual(await query.getFieldValues({ fields: [] }), { count: 0, list: [] });
  } finally {
    scope.stop();
  }
});

test('historical Trace links preserve absolute bounds, timezone and span filter', () => {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ name: 'home', path: '/trace/home', component: {} }],
  });
  const Trend = load(`${root}/components/profiling-trend.tsx`, {
    '@blueking/date-picker': { dayjs },
    'bkui-vue': {},
    'echarts/charts': {},
    'echarts/components': {},
    'echarts/core': { use: () => {} },
    'echarts/renderers': {},
    'vue-echarts': {},
    'vue-router': { useRouter: () => router },
    '../utils/flame-layout': {},
    './profiling-skeleton': {},
    '@/pages/trace-explore/components/explore-chart/use-echarts': {},
  }).default;
  const bounds = [Date.parse('2025-01-01T02:00:00Z'), Date.parse('2025-01-01T03:00:00Z')];
  const scope = vue.effectScope();
  try {
    const trend = scope.run(() => Trend.setup({ bounds, timezone: 'Asia/Shanghai', appName: 'test' }, { emit() {} }));
    const link = new URL(trend.traceHref('span&1'), 'https://example.com');
    assert.equal(link.pathname, '/trace/home');
    assert.equal(Date.parse(link.searchParams.get('start_time')), bounds[0]);
    assert.equal(Date.parse(link.searchParams.get('end_time')), bounds[1]);
    assert.equal(link.searchParams.get('timezone'), 'Asia/Shanghai');
    assert.equal(link.searchParams.get('sceneMode'), 'span');
    assert.deepEqual(JSON.parse(link.searchParams.get('where')), [
      { key: 'span_id', operator: 'equal', value: ['span&1'] },
    ]);
  } finally {
    scope.stop();
  }
});

test('Diff sorting keeps added and removed at opposite ends in both directions', () => {
  const Table = load(`${root}/components/profile-visualization/profile-table.tsx`, {
    '@blueking/tdesign-ui': {},
    'monitor-ui/chart-plugins/plugins/profiling-graph/table-graph/utils': load(
      path.join(__dirname, '../src/monitor-ui/chart-plugins/plugins/profiling-graph/table-graph/utils.ts')
    ),
    '../../utils/flame-layout': load(`${root}/utils/flame-layout.ts`, {
      'monitor-ui/chart-plugins/plugins/profiling-graph/flame-graph/utils': { COMPARE_DIFF_COLOR_LIST: [] },
      'monitor-ui/chart-plugins/typings/flame-graph': {},
      'monitor-ui/monitor-echarts/valueFormats': {},
    }),
    './profile-details': {},
    './profile-popup': {},
  }).default;
  const rows = [
    { name: 'unchanged', mark: 'unchanged', diff: 0 },
    { name: 'added', mark: 'added', diff: null },
    { name: 'increase', mark: 'changed', diff: 0.5 },
    { name: 'removed', mark: 'removed', diff: null },
    { name: 'decrease', mark: 'changed', diff: -0.5 },
  ];
  const props = vue.reactive({ rows, keyword: '', sort: { sortBy: 'diff', descending: false } });
  const scope = vue.effectScope();
  try {
    const table = scope.run(() => Table.setup(props));
    const ascending = ['added', 'decrease', 'unchanged', 'increase', 'removed'];
    assert.deepEqual(
      table.data.value.map(row => row.name),
      ascending
    );
    props.sort.descending = true;
    assert.deepEqual(
      table.data.value.map(row => row.name),
      ascending.toReversed()
    );
    assert.equal(rows[0].name, 'unchanged');
  } finally {
    scope.stop();
  }
});

test('trend tooltip restores timezone header, series units and shared styling for both axis types', () => {
  const formatted = [];
  const Trend = load(`${root}/components/profiling-trend.tsx`, {
    '@blueking/date-picker': { dayjs },
    'bkui-vue': {}, 'echarts/charts': {}, 'echarts/components': {},
    'echarts/core': { use() {} }, 'echarts/renderers': {}, 'vue-echarts': {},
    'vue-router': { useRouter: () => ({}) }, './profiling-skeleton': {},
    '../utils/flame-layout': { formatProfileValue(value, unit) {
      formatted.push([value, unit]);
      return `${value} ${unit}`;
    } },
    '@/pages/trace-explore/components/explore-chart/use-echarts': {
      createSeries: () => ({ seriesData: [], xAxis: [] }), createYAxis: () => [],
    },
  }).default;
  const props = vue.reactive({
    series: [{ unit: 'bytes', datapoints: [] }, { unit: 'count', datapoints: [] }], timezone: 'Asia/Shanghai',
    selection: false, color: '#ff9c01', legend: {},
  });
  const scope = vue.effectScope();
  try {
    const trend = scope.run(() => Trend.setup(props, { emit() {} }));
    const time = Date.parse('2026-09-24T02:13:00Z');
    const point = { axisValue: String(time), seriesName: 'alloc_space_bytes', seriesIndex: 0, color: '#ff9c01', value: 1024 };
    let tooltip = trend.options.value.tooltip;
    assert.equal(tooltip.renderMode, 'html');
    const scalar = tooltip.formatter([point, { ...point, seriesName: 'count', seriesIndex: 1, value: 0 }]);
    assert.match(scalar, /2026-09-24 10:13:00\+0800/);
    assert.match(scalar, /class="monitor-chart-tooltips"/);
    assert.match(scalar, /class="item-value"/);
    assert.match(scalar, /alloc_space_bytes:/);
    assert.deepEqual(formatted, [[1024, 'bytes'], [0, 'count']]);
    assert.equal(tooltip.formatter([{ ...point, value: null }]), '');
    assert.equal(tooltip.formatter([{ ...point, seriesId: 'selection-handles' }]), '');
    assert.match(tooltip.formatter([{ ...point, seriesName: '<img src=x onerror=alert(1)>' }]), /&lt;img/);
    props.selection = true;
    props.timezone = 'UTC';
    tooltip = trend.options.value.tooltip;
    assert.match(tooltip.formatter([{ ...point, value: [time, 512] }]), /2026-09-24 02:13:00\+0000/);
    assert.deepEqual(formatted.at(-1), [512, 'bytes']);
  } finally {
    scope.stop();
  }
});
