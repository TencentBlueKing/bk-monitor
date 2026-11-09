/* Run: node scripts/search-partial-results-test.cjs */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');
const ts = require('typescript');
const { compileTemplate, parseComponent } = require('vue/compiler-sfc');

const sourceRoot = path.resolve(__dirname, '../src');
const asDefault = value => ({ __esModule: true, default: value });
const flush = async () => {
  for (let index = 0; index < 12; index++) await Promise.resolve();
};
const deferred = () => {
  let resolve;
  const promise = new Promise(done => {
    resolve = done;
  });
  return { promise, resolve };
};
function loadSource(relativePath, dependencies = {}, globals = {}, source) {
  const file = path.join(sourceRoot, relativePath);
  const output = ts.transpileModule(source ?? fs.readFileSync(file, 'utf8'), {
    fileName: file,
    compilerOptions: {
      allowJs: true,
      jsx: ts.JsxEmit.React,
      jsxFactory: 'h',
      module: ts.ModuleKind.CommonJS,
      target: ts.ScriptTarget.ES2020,
    },
  });
  const exports = {};
  vm.runInNewContext(
    output.outputText,
    {
      exports,
      require: id => dependencies[id] ?? {},
      console,
      AbortController,
      setTimeout,
      clearTimeout,
      ...globals,
    },
    { filename: relativePath },
  );
  return exports;
}
const partial = loadSource('common/search-partial-result.ts', {}, { window: {} });
const normalizeTotal = loadSource('storage/utils/normalize-search-total.ts');
const successfulSearch = data => ({ result: true, data, rowKeys: [], size: 0 });

test('only standalone single-index page requests opt in', () => {
  assert.equal(partial.partialPageParams(false, false).allow_partial_es_results, true);
  assert.equal(partial.partialPageParams(true, false).allow_partial_es_results, undefined);
  assert.equal(partial.partialPageParams(false, true).allow_partial_es_results, undefined);
  for (const flag of ['__IS_MONITOR_COMPONENT__', '__IS_MONITOR_APM__', '__IS_MONITOR_TRACE__']) {
    const embedded = loadSource('common/search-partial-result.ts', {}, { window: { [flag]: true } });
    assert.equal(embedded.partialPageParams(false, false).allow_partial_es_results, undefined);
  }
});

function createSearchAction() {
  const defaults = () => ({ is_partial: false, is_loading: false, row_keys: [], search_count: 0, total: 0 });
  const state = {
    indexId: 'example',
    indexItem: {
      ids: ['example'],
      isUnionIndex: false,
      begin: 0,
      start_time: 1000,
      end_time: 2000,
      datePickerValue: ['1000', '2000'],
      addition: [],
      catchUnionBeginList: [],
    },
    indexFieldInfo: {},
    indexSetQueryResult: defaults(),
    unionIndexList: [],
    visibleFields: [],
    searchTotal: 0,
    tookTime: 0,
  };
  const responses = [];
  let querySequence = 0;
  const action = loadSource(
    'store/actions/retrieve-search-actions.js',
    {
      '@/common/search-partial-result': partial,
      '@/common/util': { parseBigNumberList: value => value },
      '@/storage/utils/normalize-search-total': normalizeTotal,
      '@/storage': {
        retrieveFieldCacheService: { getFieldList: () => [{ field_name: 'time' }], getFieldNameIndex: () => ({}) },
        retrieveRowCacheService: {
          createQueryKey: () => `query-${++querySequence}`,
          releaseQuery: () => {},
          clearQuery: async () => {},
          getRows: async () => [],
          gc: async () => {},
          clearMemory: () => {},
        },
        retrieveSearchWorkerService: { searchStream: () => responses.shift() },
        storageHealthService: {
          markActiveQuery: () => {},
          clearActiveQuery: () => {},
          getActiveQueryKeys: async () => [],
        },
        storeCacheService: { setApiCache: async () => {} },
      },
      '../helper.ts': {
        formatAdditionalFields: (_state, value) => value,
        getCommonFilterAdditionWithValues: () => [],
        isSceneRetrieve: () => false,
      },
      '../modules/report-helper.ts': { reportRouteLog: () => {} },
      '../request-pool.ts': asDefault({ execCanceToken: () => {}, setCancelToken: () => {} }),
    },
    { window: { AJAX_URL_PREFIX: '/api' }, document: { cookie: '' }, process: { env: {} } },
  ).requestIndexSetQueryAction;
  const commit = (name, value) => {
    if (name === 'resetIndexSetQueryResult') state.indexSetQueryResult = { ...defaults(), ...value };
    if (name === 'updateIndexSetQueryResult') Object.assign(state.indexSetQueryResult, value);
    if (name === 'updateIndexItem') Object.assign(state.indexItem, value);
  };
  const context = {
    state,
    commit,
    dispatch: async () => {},
    getters: { retrieveParams: { size: 10, addition: [] }, requestAddition: [] },
  };
  return { state, responses, run: isPagination => action(context, { isPagination }) };
}

test('empty partial lists are marked, healthy pagination retains prior partial and a new search resets it', async () => {
  const query = createSearchAction();
  query.responses.push(Promise.resolve(successfulSearch({ is_partial: true, total: 0 })));
  await query.run(false);
  assert.equal(query.state.indexSetQueryResult.is_partial, true);
  query.responses.push(Promise.resolve(successfulSearch({ is_partial: false, total: 0 })));
  await query.run(true);
  assert.equal(query.state.indexSetQueryResult.is_partial, true);
  query.responses.push(Promise.resolve(successfulSearch({ total: 0 })));
  await query.run(false);
  assert.equal(query.state.indexSetQueryResult.is_partial, false);
});

test('a stale partial list response cannot mark the newer healthy query', async () => {
  const query = createSearchAction();
  const previous = deferred();
  query.responses.push(previous.promise, Promise.resolve(successfulSearch({ total: 0 })));
  const oldSearch = query.run(false);
  await query.run(false);
  previous.resolve(successfulSearch({ status: { code: 'QUERY_RAW_PARTIAL' }, total: 0 }));
  await oldSearch;
  assert.equal(query.state.indexSetQueryResult.is_partial, false);
});

function createChart({ totalResult = { result: false }, listPartial = false, hours = 12 } = {}) {
  const callbacks = new Map();
  const timers = new Map();
  const mounted = [];
  const requests = [];
  const responses = [];
  let nextTimer = 0;
  const state = {
    indexItem: { ids: ['example'], start_time: 0, end_time: hours * 3600000, timezone: 'UTC' },
    indexFieldInfo: {},
    indexSetQueryResult: { is_partial: listPartial, total: 0 },
    storage: {},
    searchTotal: 0,
    tookTime: 0,
  };
  const store = {
    state,
    getters: {
      retrieveParams: { start_time: 0, end_time: hours * 3600000, interval: 'auto' },
      requestAddition: [],
      isUnionSearch: false,
      unionIndexList: [],
      isSceneMode: false,
    },
    commit: () => {},
    dispatch: async () => totalResult,
  };
  const h = (tag, props, ...children) => ({ tag, props, children: children.flat(Infinity) });
  const component = loadSource(
    'views/retrieve-v2/search-result-chart/index.tsx',
    {
      vue: {
        defineComponent: options => options,
        ref: value => ({ value }),
        computed: getter => ({
          get value() {
            return getter();
          },
        }),
        inject: (_key, fallback) => fallback,
        watch: () => {},
        nextTick: callback => callback(),
        onMounted: callback => mounted.push(callback),
        onBeforeUnmount: () => {},
      },
      '@/common/search-partial-result': partial,
      '@/common/util': { formatNumberWithRegex: value => String(value) },
      '@/hooks/use-locale': asDefault(() => ({ t: value => value })),
      '@/hooks/use-store': asDefault(() => store),
      '@/hooks/use-retrieve-event': asDefault(() => ({
        addEvent: (events, callback) => {
          for (const event of [].concat(events)) callbacks.set(event, callback);
        },
      })),
      '@/hooks/use-trend-chart': asDefault(() => ({
        initChartData: () => ({ interval: '1m' }),
        setChartData: () => {},
        backToPreChart: () => {},
        canGoBack: { value: false },
        cacheChartOptions: () => {},
        restoreChartOptions: () => {},
        destroyChart: () => {},
        ensureChart: async () => true,
      })),
      '@/store/helper': { formatAdditionalFields: (_state, value) => value, getCommonFilterAddition: () => [] },
      '@/store/store.type.ts': { BK_LOG_STORAGE: { TREND_CHART_IS_FOLD: 'fold' } },
      '@/storage/utils/normalize-search-total': normalizeTotal,
      '@/views/retrieve-helper': {
        ...asDefault({}),
        RetrieveEvent: new Proxy({}, { get: (_target, key) => key }),
      },
      'lodash-es': { throttle: callback => callback },
      'vue-router/composables': {
        useRoute: () => ({ params: { indexId: 'example' }, query: {} }),
        useRouter: () => ({ replace: () => {} }),
      },
      '@/api': asDefault({
        request: async (...args) => {
          requests.push(args);
          return responses.shift();
        },
      }),
    },
    {
      h,
      window: {},
      document: { body: {} },
      setTimeout: callback => {
        const id = ++nextTimer;
        timers.set(id, callback);
        return id;
      },
      clearTimeout: id => timers.delete(id),
    },
  ).default;
  const render = component.setup({}, { emit: () => {} });
  const text = () => JSON.stringify(render());
  return {
    responses,
    requests,
    text,
    start: async () => {
      for (const callback of mounted.splice(0)) callback();
      for (const [id, callback] of [...timers]) {
        timers.delete(id);
        await callback();
      }
      await flush();
    },
    reload: () => callbacks.get('TREND_GRAPH_SEARCH')(),
    cancel: () => callbacks.get('SEARCH_CANCEL')(),
    tick: async () => {
      for (const [id, callback] of [...timers]) {
        timers.delete(id);
        await callback();
      }
      await flush();
    },
  };
}

test('chart still queries after total failure and retains partial from any time segment including empty segments', async () => {
  const chart = createChart();
  chart.responses.push({ result: true, data: { is_partial: true, aggs: {} } }, { result: true, data: { aggs: {} } });
  await chart.start();
  assert.equal(chart.requests.length, 2);
  assert.match(chart.text(), /查询结果可能不完整/);
  assert.match(chart.text(), /结果总数暂不可用/);
  chart.reload();
  chart.cancel();
  assert.match(chart.text(), /查询结果可能不完整/);
  chart.reload();
  chart.responses.push({ result: true, data: { aggs: {} } }, { result: true, data: { aggs: {} } });
  await chart.tick();
  assert.doesNotMatch(chart.text(), /查询结果可能不完整/);
});

test('an empty partial list permits an independent chart query even when total reports zero', async () => {
  const chart = createChart({ listPartial: true, totalResult: { result: true, data: { total: 0 } }, hours: 1 });
  chart.responses.push({ result: true, data: { is_partial: true, aggs: {} } });
  await chart.start();
  assert.equal(chart.requests.length, 1);
  assert.match(chart.text(), /查询结果可能不完整/);
});

test('stale chart responses cannot contaminate the new query and timeout is shown as an error', async () => {
  const chart = createChart({ hours: 1 });
  const oldResponse = deferred();
  chart.responses.push(oldResponse.promise);
  await chart.start();
  chart.reload();
  chart.responses.push({ result: true, data: { aggs: {} } });
  await chart.tick();
  oldResponse.resolve({ result: true, data: { is_partial: true, aggs: {} } });
  await flush();
  assert.doesNotMatch(chart.text(), /查询结果可能不完整/);
  chart.reload();
  chart.responses.push(Promise.reject(new Error('timeout')));
  await chart.tick();
  assert.match(chart.text(), /图表查询失败，请重试/);
});

test('list notice renders independently of result rows', () => {
  const file = 'views/retrieve-v2/search-result-panel/log-result/index.vue';
  const descriptor = parseComponent(fs.readFileSync(path.join(sourceRoot, file), 'utf8'));
  const component = loadSource(
    file,
    {
      vuex: require('vuex'),
      '@/store/store.type': { BK_LOG_STORAGE: { TABLE_JSON_FORMAT: 'format' } },
    },
    { window: {}, document: { body: {} } },
    descriptor.script.content,
  ).default;
  const template = compileTemplate({ source: descriptor.template.content, filename: file, id: 'partial-list-test' });
  assert.equal(template.errors.length, 0);
  const compiled = vm.runInNewContext(`${template.code}; ({ render, staticRenderFns })`);
  const Vue = require('vue');
  const store = {
    state: { indexSetQueryResult: { is_partial: true, list: [] }, indexFieldInfo: {}, storage: {}, retrieve: {} },
    getters: {},
  };
  const view = new Vue({
    ...component,
    ...compiled,
    propsData: { retrieveParams: {} },
    beforeCreate() {
      this.$store = store;
      this.$route = { params: {} };
      this.$t = value => value;
    },
  });
  const texts = node => [node?.text ?? '', ...(node?.children ?? []).flatMap(texts)].join('');
  assert.match(texts(view._render()), /查询结果可能不完整/);
  store.state.indexSetQueryResult.is_partial = false;
  assert.doesNotMatch(texts(view._render()), /查询结果可能不完整/);
});
