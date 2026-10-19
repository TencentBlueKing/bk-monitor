const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const ts = require('typescript');
const vue = require('../src/trace/node_modules/vue');
const root = path.resolve(__dirname, '../src/trace/pages/main');

global.window = { i18n: { t: value => value } };
global.localStorage = {
  values: new Map(),
  getItem(key) { return this.values.get(key) ?? null; },
  setItem(key, value) { this.values.set(key, value); },
};

function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((res, rej) => { resolve = res; reject = rej; });
  return { promise, resolve, reject };
}
const flush = async () => { await Promise.resolve(); await vue.nextTick(); await Promise.resolve(); };

function sourceLoader(listFlows = () => Promise.resolve({ traces: [] }), instrument) {
  const modules = new Map();
  const loadSource = file => {
    if (modules.has(file)) return modules.get(file);
    const result = ts.transpileModule(fs.readFileSync(file, 'utf8'), {
      compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
    }).outputText;
    const module = { exports: {} };
    const load = id => {
      if (id === 'vue') return vue;
      if (id === 'vue-i18n') return { useI18n: () => ({ t: value => value }) };
      if (id === '@vueuse/core') return { get: vue.unref };
      if (id === 'monitor-api/modules/llm_web') return { listFlows };
      if (id === 'monitor-api/cancel') return { CancelToken: class { constructor(fn) { fn(() => {}); } } };
      if (id.endsWith('/utils/date')) return { formatDuration: value => `${value}μs` };
      if (id.endsWith('/utils/config/get-config')) return { getConfigValue: () => [] };
      if (id === './trace-viewer') return { getTraceName: () => 'test-trace' };
      if (id.startsWith('.')) {
        const target = path.resolve(path.dirname(file), id);
        return loadSource([`${target}.ts`, `${target}.tsx`, `${target}.js`].find(fs.existsSync));
      }
      return require(id);
    };
    new Function('require', 'module', 'exports', result)(load, module, module.exports);
    instrument?.(file, module.exports);
    modules.set(file, module.exports);
    return module.exports;
  };
  return loadSource;
}

function flowResponse(traceId = 'trace-a', input) {
  return {
    input_tokens: 12,
    traces: [{ trace_id: traceId, conversation_id: 'conversation-a', input: input || '', flow: [{
      trace_id: traceId, span_id: 'span-a', span_name: 'chat', start_time: 100, end_time: 200, elapsed_time: 100,
      attributes: { 'gen_ai.operation.name': 'chat', 'gen_ai.usage.input_tokens': 12 },
      ...(input === undefined ? {} : { input, output: 'answer' }),
    }] }],
  };
}

function createObservation(instrument) {
  const requests = [];
  const load = sourceLoader(params => {
    const pending = deferred();
    requests.push({ params, ...pending });
    return pending.promise;
  }, instrument);
  const { useLlmObservation } = load(path.join(root, 'inquire-content/llm-observation/hooks/use-llm-observation.ts'));
  const scope = vue.effectScope();
  const context = { appName: vue.shallowRef('app-a'), bizId: vue.shallowRef(11), traceId: vue.shallowRef('trace-a') };
  const result = scope.run(() => useLlmObservation(context));
  return { result, context, requests, stop: () => scope.stop() };
}

test('execution rows prioritize model, tool and Agent names and retain distinct Span names', () => {
  const load = sourceLoader();
  const { flattenVisibleSpanRows } = load(path.join(root, 'inquire-content/llm-observation/utils/transform.ts'));
  const cases = [
    [
      'chat',
      { 'gen_ai.request.model': 'requested-model', 'gen_ai.response.model': 'gpt-6.1-sol' },
      'chat gpt-6.1-sol', 'gpt-6.1-sol', 'chat gpt-6.1-sol',
    ],
    ['chat', { 'gen_ai.request.model': 'deepseek-v4.1-flash-ioa' }, 'chat', 'deepseek-v4.1-flash-ioa', 'chat'],
    [
      'execute_tool', { 'gen_ai.tool.name': 'functions.exec' },
      'execute functions.exec', 'functions.exec', 'execute functions.exec',
    ],
    ['invoke_agent', { 'gen_ai.agent.name': 'Codex' }, 'agent.run', 'Codex', 'agent.run'],
    ['invoke_agent', { 'gen_ai.agent.name': 'Codex' }, 'Codex', 'Codex', ''],
    ['chat', {}, 'chat', 'chat', ''],
    ['execute_tool', {}, 'execute tool', 'execute tool', ''],
    ['invoke_agent', {}, 'agent.run', 'agent.run', ''],
  ];
  for (const [operation, attributes, spanName, expectedName, expectedSubtitle] of cases) {
    const span = {
      ...flowResponse().traces[0].flow[0],
      span_name: spanName,
      attributes: { ...attributes, 'gen_ai.operation.name': operation },
    };
    const [row] = flattenVisibleSpanRows([span], { expandedSpanIds: new Set(), filter: 'all', keyword: '' });
    assert.equal(row.name, expectedName);
    assert.equal(row.subtitle, expectedSubtitle);
    assert.equal(flattenVisibleSpanRows([span], { expandedSpanIds: new Set(), filter: 'all', keyword: spanName }).length, 1);
  }
});

test('execution line appears from lightweight result while IO is pending, then merges by span id', async () => {
  const { result, requests, stop } = createObservation();
  assert.equal(requests.length, 2);
  const light = requests.find(r => r.params.include_input_output === false);
  const io = requests.find(r => r.params.include_input_output === true);
  assert.equal(io.params.input_output_preview, true);
  light.resolve(flowResponse());
  await flush();
  assert.equal(result.loading.value, false);
  assert.equal(result.hasTraces.value, true);
  assert.equal(result.traceBlocks.value[0].rows[0].ioLoading, true);
  io.resolve(flowResponse('trace-a', 'question'));
  await flush();
  const row = result.traceBlocks.value[0].rows[0];
  assert.equal(row.ioLoading, false);
  assert.equal(row.io.input[0].text, 'question');
  assert.equal(row.rawSpan, undefined);
  assert.equal(row.attributes, undefined);
  stop();
});

test('IO arriving first is preserved and IO failure does not clear lightweight execution line', async () => {
  const one = createObservation();
  one.requests.find(r => r.params.include_input_output).resolve(flowResponse('trace-a', 'first'));
  await flush();
  assert.equal(one.result.hasTraces.value, true);
  assert.equal(one.result.loading.value, false);
  one.requests.find(r => !r.params.include_input_output).resolve(flowResponse());
  await flush();
  assert.equal(one.result.traceBlocks.value[0].rows[0].io.input[0].text, 'first');
  one.stop();
  const two = createObservation();
  two.requests.find(r => !r.params.include_input_output).resolve(flowResponse());
  two.requests.find(r => r.params.include_input_output).reject(new Error('IO unavailable'));
  await flush();
  assert.equal(two.result.hasTraces.value, true);
  assert.equal(two.result.traceBlocks.value[0].rows[0].ioLoading, false);
  two.stop();
});

test('late responses from a previous Trace cannot replace current structure or IO', async () => {
  const { result, requests, context, stop } = createObservation();
  const old = requests.slice();
  context.traceId.value = 'trace-b';
  await flush();
  for (const request of requests.slice(2)) request.resolve(flowResponse('trace-b', request.params.include_input_output ? 'new' : undefined));
  await flush();
  for (const request of old) request.resolve(flowResponse('trace-a', 'obsolete'));
  await flush();
  assert.equal(result.traceBlocks.value[0].traceId, 'trace-b');
  assert.equal(result.traceBlocks.value[0].rows[0].io.input[0].text, 'new');
  stop();
});

test('app preferences default to LLM, remember waterfall, isolate businesses, and respect a manual pending selection', async () => {
  localStorage.values.clear();
  const load = sourceLoader();
  const { useTracePanelPreference } = load(path.join(root, 'inquire-content/llm-observation/hooks/use-trace-panel-preference.ts'));
  const context = { appName: vue.shallowRef('app-a'), bizId: vue.shallowRef(11), traceId: vue.shallowRef('trace-a'), hasLlmTraces: vue.shallowRef(false), llmLoading: vue.shallowRef(true) };
  const scope = vue.effectScope();
  const result = scope.run(() => useTracePanelPreference(context));
  context.hasLlmTraces.value = true;
  await flush();
  assert.equal(result.panel.value, 'llm');
  result.selectPanel('timeline');
  context.traceId.value = 'trace-b';
  await flush();
  assert.equal(result.panel.value, 'timeline');
  context.bizId.value = 12;
  context.hasLlmTraces.value = false;
  await flush();
  context.hasLlmTraces.value = true;
  await flush();
  assert.equal(result.panel.value, 'llm');
  context.traceId.value = 'trace-c';
  context.hasLlmTraces.value = false;
  await flush();
  result.selectPanel('topo');
  context.hasLlmTraces.value = true;
  await flush();
  assert.equal(result.panel.value, 'topo');
  scope.stop();
});

// 执行源码中的入口函数，验证请求未结束时的挂载状态与异常后的 Loading。
function loadFunction(file, name, dependencies, prelude = '') {
  const source = ts.createSourceFile(file, fs.readFileSync(file, 'utf8'), ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  let initializer;
  function find(node) {
    if (ts.isVariableDeclaration(node) && node.name.getText(source) === name) initializer = node.initializer.getText(source);
    if (ts.isFunctionDeclaration(node) && node.name?.getText(source) === name) initializer = node.getText(source);
    ts.forEachChild(node, find);
  }
  find(source);
  assert.ok(initializer, name);
  const code = ts.transpileModule(`${prelude}\nmodule.exports = ${initializer}`, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS } }).outputText;
  const module = { exports: {} };
  new Function(...Object.keys(dependencies), 'module', code)(...Object.values(dependencies), module);
  return module.exports;
}

test('waterfall auto-fit measures repeated names once and stops once its width cap is reached', () => {
  const file = path.resolve(root, '../../components/trace-view/trace-timeline-viewer/index.tsx');
  const width = { value: 0 };
  const spans = { value: Array.from({ length: 72043 }, () => ({
    depth: 1, service_name: 'service', operationName: 'operation',
  })) };
  let measures = 0;
  const autoFit = loadFunction(file, 'getAutoFitColumnWidth', {
    wrapperRef: { value: { getBoundingClientRect: () => ({ width: 1000 }) } },
    spans, spanNameColumnWidth: width, minSpanNameColumnWidth: { value: 0.25 },
    AUTO_FIT_MAX_RATIO: 0.8, INDENT_PER_DEPTH: 29, SPAN_NAME_EXTRA_WIDTH: 112,
    getComputedStyle: () => ({ fontFamily: 'monospace' }),
    measureTextWidth: () => { measures++; return 100; },
  });
  autoFit();
  assert.equal(measures, 2);
  assert.equal(width.value, 0.37);
  spans.value[0].depth = 100;
  measures = 0;
  autoFit();
  assert.equal(measures, 2);
  assert.equal(width.value, 0.8);
});

test('virtualized Trace list redraws through the public Vue instance in production', async () => {
  let redraw;
  let renders = 0;
  const renderer = vue.createRenderer({
    createElement: tag => ({ tag, children: [] }),
    createText: text => ({ text }),
    createComment: text => ({ text }),
    insert: (child, parent) => parent.children.push(child),
    remove() {},
    setElementText: (element, text) => { element.text = text; },
    setText: (element, text) => { element.text = text; },
    parentNode: () => null,
    nextSibling: () => null,
    patchProp() {},
  });
  const app = renderer.createApp(vue.defineComponent({
    setup() {
      const internalInstance = vue.getCurrentInstance();
      if (process.env.NODE_ENV === 'production') assert.equal(internalInstance.ctx.$forceUpdate, undefined);
      redraw = loadFunction(path.resolve(root, '../../components/trace-view/trace-timeline-viewer/list-view/index.tsx'), 'forceUpdate', {
        internalInstance,
      });
      return () => { renders++; return vue.h('div', String(renders)); };
    },
  }));
  app.mount({ children: [] });
  assert.equal(renders, 1);
  redraw();
  await vue.nextTick();
  assert.equal(renders, 2);
  app.unmount();
});

test('precise Trace query mounts detail and publishes context before trace_detail resolves', async () => {
  const pending = deferred();
  const state = { app: 'app-a', searchType: 'accurate', isAlreadyAccurateQuery: false };
  const store = { loading: false, selectedTraceViewFilterTab: '', setPageLoading(v) { this.loading = v; }, setTraceData(v) { this.traceData = v; } };
  const query = loadFunction(path.join(root, 'inquire.tsx'), 'handleQueryTraceId', {
    state, store, isLoading: { value: false }, traceIDSearchValue: { value: 'trace-a' }, searchIdType: { value: 'traceID' },
    router: { replace() {} }, route: { name: 'home' }, traceDetail: () => pending.promise, spanDetail() {},
    traceViewFilters: { value: [] }, searchResultIdType: { value: 'spanID' }, DEFAULT_TRACE_DATA: { original_data: [] }, QUERY_TRACE_RELATION_APP: 'query_trace_relation_app',
  }, 'let accurateRequestId = 0;');
  const run = query();
  assert.equal(state.isAlreadyAccurateQuery, true);
  assert.equal(store.traceData.trace_id, 'trace-a');
  assert.equal(store.traceData.appName, 'app-a');
  assert.equal(store.loading, true);
  pending.resolve({ original_data: [{ span_id: 'span-a' }] });
  await run;
  assert.equal(store.loading, false);
  assert.equal(store.traceData.original_data.length, 1);
});

test('list detail query clears Loading when trace_detail fails', async () => {
  const store = { traceViewFilters: [], setTraceDetail() {}, setTraceLoaidng(v) { this.loading = v; }, setTraceData(v) { this.data = v; } };
  const query = loadFunction(path.join(root, 'inquire-content/trace-list.tsx'), 'getTraceDetails', {
    store, searchCancelFn() {}, curTraceId: { value: '' }, props: { appName: 'app-a' }, traceDetailElem: { value: null },
    traceDetail: () => Promise.reject(new Error('failed')), CancelToken: class {}, DEFAULT_TRACE_DATA: { original_data: [] }, QUERY_TRACE_RELATION_APP: 'query_trace_relation_app',
  }, 'let detailRequestId = 0;');
  await query('trace-a');
  assert.equal(store.loading, false);
  assert.equal(store.data.trace_id, 'trace-a');
});


test('compact grouping shares one member array and keeps old expand/collapse behavior', () => {
  const load = sourceLoader();
  const transformTraceTree = load(path.resolve(root, '../../components/trace-view/model/transform-trace-data.tsx')).default;
  const { handleTraceTreeGroup, handleToggleCollapse } = load(path.resolve(root, '../../components/trace-view/utils/group.tsx'));
  const members = ['span-a', 'span-b', 'span-c'];
  const fixture = compact => ({
    traceID: 'trace-a', processes: { service: { serviceName: 'service', tags: [] } },
    spans: members.map((id, index) => ({
      spanID: id, traceID: 'trace-a', startTime: 100 + index, duration: 10, processID: 'service', operationName: 'operation',
      references: [], group_info: { id: 'span-a', duration: 12, members: compact && index > 0 ? [] : [...members] },
    })),
  });
  const compact = transformTraceTree(fixture(true)).spans;
  const full = transformTraceTree(fixture(false)).spans;
  assert.strictEqual(compact[0].group_info, compact[1].group_info);
  assert.strictEqual(compact[1].group_info, compact[2].group_info);
  assert.deepEqual(compact[0].group_info.members, members);
  for (const spans of [compact, full]) {
    assert.deepEqual(handleTraceTreeGroup(spans).map(s => s.span_id), ['span-a']);
    assert.deepEqual(handleTraceTreeGroup(handleToggleCollapse(spans, 'span-a', 'expand')).map(s => s.span_id), members);
    assert.deepEqual(handleTraceTreeGroup(handleToggleCollapse(spans, 'span-a', 'collpase')).map(s => s.span_id), ['span-a']);
  }
});


test('empty and failed queries show an empty state only after both independent sources finish', async () => {
  for (const fail of [false, true]) {
    const observation = createObservation();
    const traceTree = vue.shallowRef({ spans: [] });
    const isLoading = vue.shallowRef(true);
    const store = vue.reactive({ loading: false });
    const isEmpty = loadFunction(path.join(root, 'inquire-content/trace-detail.tsx'), 'isEmpty', {
      computed: vue.computed, isLoading, store, llmObservation: observation.result, traceTree,
    });
    assert.equal(isEmpty.value, false);
    for (const request of observation.requests) {
      if (fail) request.reject(new Error('unavailable'));
      else request.resolve({ traces: [] });
    }
    await flush();
    assert.equal(isEmpty.value, false);
    isLoading.value = false;
    assert.equal(isEmpty.value, true);
    observation.stop();
  }
});

test('list detail query ignores an older response and keeps Loading for the current request', async () => {
  const requests = [];
  const store = { traceViewFilters: [], setTraceDetail() {}, setTraceLoaidng(v) { this.loading = v; }, setTraceData(v) { this.data = v; } };
  const query = loadFunction(path.join(root, 'inquire-content/trace-list.tsx'), 'getTraceDetails', {
    store, searchCancelFn() {}, curTraceId: { value: '' }, props: { appName: 'app-a' }, traceDetailElem: { value: null },
    traceDetail: () => { const request = deferred(); requests.push(request); return request.promise; },
    CancelToken: class {}, DEFAULT_TRACE_DATA: { original_data: [] }, QUERY_TRACE_RELATION_APP: 'query_trace_relation_app',
  }, 'let detailRequestId = 0;');
  const first = query('trace-a');
  const second = query('trace-b');
  requests[0].resolve({ original_data: [{ span_id: 'obsolete' }] });
  await first;
  assert.equal(store.data.trace_id, 'trace-b');
  assert.equal(store.data.original_data.length, 0);
  assert.equal(store.loading, true);
  requests[1].resolve({ original_data: [{ span_id: 'current' }] });
  await second;
  assert.equal(store.data.trace_id, 'trace-b');
  assert.equal(store.loading, false);
});


test('a ready LLM response at initial preference setup selects LLM immediately', () => {
  localStorage.values.clear();
  const load = sourceLoader();
  const { useTracePanelPreference } = load(path.join(root, 'inquire-content/llm-observation/hooks/use-trace-panel-preference.ts'));
  const scope = vue.effectScope();
  const result = scope.run(() => useTracePanelPreference({ appName: 'app-ready', bizId: 11, traceId: 'trace-ready', hasLlmTraces: true, llmLoading: false }));
  assert.equal(result.panel.value, 'llm');
  scope.stop();
});


test('actual Trace store skips cloning empty cross_relation while preserving raw data for expandable relations', async () => {
  const load = sourceLoader();
  const transformTraceTree = load(path.resolve(root, '../../components/trace-view/model/transform-trace-data.tsx')).default;
  const { handleTraceTreeGroup } = load(path.resolve(root, '../../components/trace-view/utils/group.tsx'));
  for (const crossRelation of [{}, { trace_id: 'related-trace', app_name: 'related-app', permission: true }]) {
    let clones = 0;
    const traceData = vue.shallowRef({});
    const traceTree = vue.shallowRef({});
    const originTraceTree = vue.shallowRef({});
    const setTraceData = loadFunction(path.resolve(root, '../../store/modules/trace.ts'), 'setTraceData', {
      traceData, traceTree, originTraceTree, originCrossAppSpanMaps: vue.shallowRef({}), spanGroupTree: vue.shallowRef([]),
      setServiceSpanList() {}, transformTraceTree, handleTraceTreeGroup, markRaw: vue.markRaw,
      deepClone(value) { clones++; return structuredClone(value); },
    });
    const rawTree = { traceID: 'trace-a', processes: { service: { serviceName: 'service', tags: [] } }, spans: [{
      spanID: 'span-a', startTime: 100, duration: 10, processID: 'service', references: [], cross_relation: crossRelation,
    }] };
    setTraceData({ trace_tree: rawTree, appName: 'app-a', original_data: [], span_classify: [] });
    assert.equal(clones, crossRelation.trace_id ? 1 : 0);
    assert.equal(traceTree.value.spans.length, 1);
    if (crossRelation.trace_id) {
      assert.strictEqual(originTraceTree.value, rawTree);
      assert.equal(rawTree.spans[0].span_id, undefined);
    } else {
      assert.equal(originTraceTree.value.spans.length, 0);
      assert.strictEqual(traceTree.value.spans[0], rawTree.spans[0]);
    }
    let nestedReads = 0;
    Object.defineProperty(traceTree.value.spans[0], 'inspectionOnly', {
      enumerable: true, get() { nestedReads++; return 'nested'; },
    });
    let rootUpdates = 0;
    const stop = vue.watch(traceTree, () => rootUpdates++, { deep: true });
    assert.equal(nestedReads, 0);
    setTraceData({ trace_tree: { spans: [] }, appName: 'app-a' });
    await vue.nextTick();
    assert.equal(rootUpdates, 1);
    assert.equal(nestedReads, 0);
    assert.deepEqual(traceTree.value, { spans: [] });
    stop();
  }
});


test('session overview keeps cached current flow and loads related Trace previews independently', async () => {
  const { result, requests, stop } = createObservation();
  requests.find(r => !r.params.include_input_output).resolve(flowResponse());
  requests.find(r => r.params.include_input_output).resolve(flowResponse('trace-a', 'current'));
  await flush();
  result.handleSessionChange(true);
  await flush();
  const overview = { traces: Array.from({ length: 6 }, (_, i) => ({ trace_id: i ? `related-${i}` : 'trace-a', flow: [] })) };
  for (const request of requests.slice(2, 4)) request.resolve(overview);
  await flush();
  assert.equal(requests.length, 4);
  assert.equal(result.traceBlocks.value.length, 6);
  result.toggleTrace('related-1');
  assert.equal(requests.length, 6);
  const detail = requests.slice(4);
  detail.find(r => r.params.include_input_output).resolve(flowResponse('related-1', 'related input'));
  detail.find(r => !r.params.include_input_output).resolve(flowResponse('related-1'));
  await flush();
  const related = result.traceBlocks.value.find(t => t.traceId === 'related-1');
  assert.equal(related.rows[0].io.input[0].text, 'related input');
  assert.equal(related.flowLoading, false);
  stop();
});

test('a late Span detail response does not rewrite the currently selected Span', async () => {
  const requests = [];
  const selected = { span_id: 'span-a', llm_detail: { span_type: 'LLM' } };
  const props = { show: true, spanDetails: selected };
  const rendered = [];
  const prepare = loadFunction(path.join(root, 'span-details.tsx'), 'prepareDetails', {
    props, loadedSpan: vue.shallowRef(null), shouldLoadSpanDetail: () => true,
    loadSpanDetail: () => { const pending = deferred(); requests.push(pending); return pending.promise; },
    getDetails: value => rendered.push(value),
  });
  const first = prepare();
  props.spanDetails = { span_id: 'span-b', llm_detail: { span_type: 'LLM' } };
  const second = prepare();
  requests[1].resolve({ span_id: 'span-b', attributes: { content: 'current' } });
  await second;
  requests[0].resolve({ span_id: 'span-a', attributes: { content: 'obsolete' } });
  await first;
  assert.equal(rendered.length, 1);
  assert.equal(rendered[0].span_id, 'span-b');
});

test('LLM is usable while trace_detail remains pending, and waterfall retains its own Loading', () => {
  const state = vue.reactive({ activePanel: 'llm' });
  const pageLoading = loadFunction(path.join(root, 'inquire-content/trace-detail.tsx'), 'pageLoading', {
    computed: vue.computed, state, isLoading: vue.shallowRef(true), store: { loading: true },
    traceTree: vue.shallowRef({ spans: [] }),
    llmObservation: { hasTraces: vue.shallowRef(true), loading: vue.shallowRef(false), ioLoading: vue.shallowRef(true) },
  });
  assert.equal(pageLoading.value, false);
  state.activePanel = 'timeline';
  assert.equal(pageLoading.value, true);
});


test('Trace detail layout watcher follows reference replacements without traversing Span payloads', async () => {
  const file = path.join(root, 'inquire-content/trace-detail.tsx');
  const source = ts.createSourceFile(file, fs.readFileSync(file, 'utf8'), ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  let expression;
  function find(node) {
    if (ts.isCallExpression(node) && node.expression.getText(source) === 'watch' && node.arguments[0]?.body?.getText(source) === 'traceData.value') expression = node.getText(source);
    ts.forEachChild(node, find);
  }
  find(source);
  assert.ok(expression);
  const code = ts.transpileModule(`module.exports = () => ${expression}`, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS } }).outputText;
  let calls = 0;
  const module = { exports: {} };
  const traceData = vue.shallowRef({ original_data: [{ attributes: { text: 'first' } }] });
  const dependencies = { watch: vue.watch, traceData, cancelFilter: () => { calls++; }, state: {}, clearCompareParams() {}, nextTick: vue.nextTick, handleResize() {}, compareSelect: { value: null } };
  new Function(...Object.keys(dependencies), 'module', code)(...Object.values(dependencies), module);
  const scope = vue.effectScope();
  scope.run(module.exports);
  traceData.value.original_data[0].attributes.text = 'mutation';
  await flush();
  assert.equal(calls, 0);
  traceData.value = { original_data: [] };
  await flush();
  assert.equal(calls, 1);
  scope.stop();
});

test('compact ordinary and LLM spans load detail while complete same-app spans keep their existing path', () => {
  const shouldLoad = loadFunction(path.join(root, 'span-details.tsx'), 'shouldLoadSpanDetail', {
    viewAppName: { value: 'app-a' }, viewBizId: { value: 11 },
  });
  const span = { span_id: 'span-a', app_name: 'app-a', bk_biz_id: 11, operationName: 'chat', startTime: 100, attributes: [{ key: 'span.kind', value: 1 }] };
  assert.equal(shouldLoad(span), false);
  assert.equal(shouldLoad({ ...span, attributes: [] }), true);
  assert.equal(shouldLoad({ ...span, attributes: undefined }), true);
  assert.equal(shouldLoad({ ...span, app_name: 'other-app' }), true);
  assert.equal(shouldLoad({ ...span, bk_biz_id: 12 }), true);
  assert.equal(shouldLoad({ ...span, llm_detail: { span_type: 'LLM' } }), true);
  assert.equal(shouldLoad({ ...span, llm_detail: { span_type: 'LLM', llm_detail: { span_type: 'LLM' } } }), true);
  assert.equal(shouldLoad({ ...span, llm_detail: { span_type: 'LLM', attributes: { input: 'complete' } } }), false);
});

test('lazy Span detail request uses the Span app context and returns full data without another time filter', async () => {
  const load = sourceLoader();
  const transformTraceTree = load(path.resolve(root, '../../components/trace-view/model/transform-trace-data.tsx')).default;
  const loadedSpan = vue.shallowRef(null);
  const requests = [];
  const originData = { span_id: 'span-a', attributes: { 'gen_ai.input.messages': [{ role: 'user', content: 'full question' }] } };
  const fullSpan = {
    spanID: 'span-a', traceID: 'trace-a', app_name: 'related-app', bk_biz_id: 12,
    startTime: 100, duration: 10, processID: 'service', operationName: 'chat', references: [],
    llm_detail: { span_type: 'LLM', attributes: originData.attributes },
  };
  const loadSpanDetail = loadFunction(path.join(root, 'span-details.tsx'), 'loadSpanDetail', {
    loadedSpan, spanDetailLoading: vue.shallowRef(false), viewBizId: { value: 11 }, viewAppName: { value: 'app-a' },
    spanDetail: async params => { requests.push(params); return { origin_data: originData, trace_tree: { traceID: 'trace-a', processes: { service: { serviceName: 'service', tags: [] } }, spans: [fullSpan] } }; },
    transformTraceTree, CancelToken: class { constructor(fn) { fn(() => {}); } },
  }, 'let spanDetailRequestKey = ""; let spanDetailRequestSeq = 0; let spanDetailCancel = null; let spanDetailResponseCache = null;');
  const response = await loadSpanDetail({ span_id: 'span-a', bk_biz_id: 12, app_name: 'related-app', llm_detail: { span_type: 'LLM' } });
  assert.deepEqual(requests, [{ bk_biz_id: 12, app_name: 'related-app', span_id: 'span-a' }]);
  assert.strictEqual(response, originData);
  assert.equal(loadedSpan.value.lazy, undefined);
  assert.equal(loadedSpan.value.llm_detail.attributes['gen_ai.input.messages'][0].content, 'full question');
});


test('an explicit waterfall choice made while LLM data is pending is cached for the application', async () => {
  localStorage.values.clear();
  const load = sourceLoader();
  const { useTracePanelPreference } = load(path.join(root, 'inquire-content/llm-observation/hooks/use-trace-panel-preference.ts'));
  const scope = vue.effectScope();
  const context = { appName: 'pending-app', bizId: 11, traceId: vue.shallowRef('trace-a'), hasLlmTraces: vue.shallowRef(false), llmLoading: vue.shallowRef(true) };
  const preference = scope.run(() => useTracePanelPreference(context));
  preference.selectPanel('timeline');
  assert.equal(localStorage.getItem('trace_detail_panel:11:pending-app'), 'timeline');
  context.hasLlmTraces.value = true;
  await flush();
  assert.equal(preference.panel.value, 'timeline');
  scope.stop();
});


test('direct-link same-app initialization does not invalidate the active accurate query; changing app does', async () => {
  const file = path.join(root, 'inquire.tsx');
  const source = ts.createSourceFile(file, fs.readFileSync(file, 'utf8'), ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  const functions = {};
  function find(node) {
    if (ts.isVariableDeclaration(node) && node.name.getText(source) === 'handleQueryTraceId') functions.query = node.initializer.getText(source);
    if (ts.isFunctionDeclaration(node) && node.name?.getText(source) === 'handleAppSelectChange') functions.changeApp = node.getText(source);
    ts.forEachChild(node, find);
  }
  find(source);
  const code = ts.transpileModule(`let accurateRequestId=0; const query=${functions.query}; const changeApp=${functions.changeApp}; module.exports={query,changeApp};`, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS } }).outputText;
  const pending = [];
  const state = { app: 'app-a', searchType: 'accurate', isAlreadyAccurateQuery: false };
  const store = { loading: false, selectedTraceViewFilterTab: '', setPageLoading(v) { this.loading = v; }, setTraceData(v) { this.traceData = v; } };
  const dependencies = {
    state, store, isLoading: { value: false }, traceIDSearchValue: { value: 'trace-a' }, searchIdType: { value: 'traceID' },
    router: { replace() {} }, route: { name: 'home' }, traceDetail: () => { const request=deferred(); pending.push(request); return request.promise; }, spanDetail() {},
    traceViewFilters: { value: [] }, searchResultIdType: { value: 'traceID' }, DEFAULT_TRACE_DATA: { original_data: [] }, QUERY_TRACE_RELATION_APP: 'query_trace_relation_app',
    traceListPagination: {}, traceColumnFilters: { value: {} }, scopeSelects: { value: { service: {} } }, searchStore: { getPanelList() {} },
  };
  const module = { exports: {} };
  new Function(...Object.keys(dependencies), 'module', code)(...Object.values(dependencies), module);
  const first=module.exports.query();
  await module.exports.changeApp('app-a');
  assert.equal(store.loading,true);
  pending[0].resolve({ original_data: [{ span_id: 'current' }] });
  await first;
  assert.equal(store.traceData.original_data[0].span_id,'current');
  const second=module.exports.query();
  await module.exports.changeApp('app-b');
  pending[1].resolve({ original_data: [{ span_id: 'stale' }] });
  await second;
  assert.equal(store.traceData.original_data.length,0);
});

test('returning to a cached Span invalidates another pending detail response', async () => {
  const load = sourceLoader();
  const transformTraceTree = load(path.resolve(root, '../../components/trace-view/model/transform-trace-data.tsx')).default;
  const loadedSpan = vue.shallowRef(null);
  const spanDetailLoading = vue.shallowRef(false);
  const requests = [];
  let cancelled = 0;
  const loadDetail = loadFunction(path.join(root, 'span-details.tsx'), 'loadSpanDetail', {
    loadedSpan, spanDetailLoading, viewBizId: { value: 11 }, viewAppName: { value: 'app-a' }, transformTraceTree,
    spanDetail: params => { const pending = deferred(); requests.push({ params, ...pending }); return pending.promise; },
    CancelToken: class { constructor(fn) { fn(() => { cancelled++; }); } },
  }, 'let spanDetailRequestKey = ""; let spanDetailRequestSeq = 0; let spanDetailCancel = null; let spanDetailResponseCache = null;');
  const response = id => ({ origin_data: { span_id: id }, trace_tree: {
    traceID: 'trace-a', processes: { service: { serviceName: 'service', tags: [] } }, spans: [{
      spanID: id, traceID: 'trace-a', startTime: 100, duration: 10, processID: 'service', operationName: id, references: [],
    }],
  } });
  const spanA = { span_id: 'span-a', llm_detail: { span_type: 'LLM' } };
  const initial = loadDetail(spanA);
  requests[0].resolve(response('span-a'));
  await initial;
  const pendingB = loadDetail({ span_id: 'span-b', llm_detail: { span_type: 'LLM' } });
  await loadDetail(spanA);
  assert.equal(loadedSpan.value.span_id, 'span-a');
  assert.equal(spanDetailLoading.value, false);
  assert.ok(cancelled > 0);
  requests[1].resolve(response('span-b'));
  await pendingB;
  assert.equal(loadedSpan.value.span_id, 'span-a');
});

test('conversation fallback visits nested spans once and preserves depth-first priority', () => {
  const load = sourceLoader();
  const { pickConversationId } = load(path.join(root, 'inquire-content/llm-observation/utils/transform.ts'));
  let reads = 0;
  let chain = [];
  for (let index = 199; index >= 0; index--) {
    const node = { span_id: String(index), childs: chain };
    Object.defineProperty(node, 'attributes', { get() { reads++; return {}; } });
    chain = [node];
  }
  assert.equal(pickConversationId([{ trace_id: 'trace-a', flow: chain }]), '');
  assert.equal(reads, 200);
  assert.equal(pickConversationId([{ trace_id: 'trace-a', flow: [{ attributes: {}, childs: [
    { attributes: { 'gen_ai.conversation.id': 'nested-first' } },
  ] }, { attributes: { 'gen_ai.conversation.id': 'sibling-second' } }] }]), 'nested-first');
  assert.equal(pickConversationId([{ trace_id: 'trace-a', conversation_id: 'overview-first', flow: chain }]), 'overview-first');
});


test('IO completion reuses structure work while filters and expansion still update rows', async () => {
  let builds = 0;
  let flattens = 0;
  const observation = createObservation((file, exports) => {
    if (!file.endsWith('/llm-observation/utils/transform.ts')) return;
    const build = exports.buildTraceView;
    const flatten = exports.flattenVisibleSpanRows;
    exports.buildTraceView = (...args) => { builds++; return build(...args); };
    exports.flattenVisibleSpanRows = (...args) => { flattens++; return flatten(...args); };
  });
  const { result, requests, stop } = observation;
  const response = input => {
    const data = flowResponse('trace-a', input);
    data.traces[0].flow = [{
      trace_id: 'trace-a', span_id: 'agent', span_name: 'agent', start_time: 100, end_time: 200, elapsed_time: 100,
      attributes: { 'gen_ai.operation.name': 'invoke_agent' }, childs: data.traces[0].flow,
    }];
    return data;
  };
  requests.find(request => !request.params.include_input_output).resolve(response());
  await flush();
  const structure = rows => rows.map(({ io, ioLoading, ...row }) => row);
  const initial = structure(result.traceBlocks.value[0].rows);
  assert.equal(initial.length, 2);
  const counts = [builds, flattens];
  requests.find(request => request.params.include_input_output).resolve(response('question'));
  await flush();
  assert.deepEqual(structure(result.traceBlocks.value[0].rows), initial);
  assert.equal(result.traceBlocks.value[0].rows[1].io.input[0].text, 'question');
  assert.deepEqual([builds, flattens], counts);
  result.toggleSpan('agent');
  assert.equal(result.traceBlocks.value[0].rows.length, 1);
  result.toggleSpan('agent');
  assert.equal(result.traceBlocks.value[0].rows.length, 2);
  result.filter.value = 'tool';
  assert.equal(result.traceBlocks.value[0].rows.length, 0);
  result.filter.value = 'llm';
  assert.equal(result.traceBlocks.value[0].rows.length, 2);
  result.keyword.value = 'not-present';
  assert.equal(result.traceBlocks.value[0].rows.length, 0);
  result.keyword.value = 'chat';
  assert.equal(result.traceBlocks.value[0].rows.length, 2);
  stop();
});

function createPreference() {
  localStorage.values.clear();
  localStorage.setItem('trace_detail_panel:11:app-a', 'timeline');
  const load = sourceLoader();
  const { useTracePanelPreference } = load(path.join(root, 'inquire-content/llm-observation/hooks/use-trace-panel-preference.ts'));
  const context = { appName: vue.shallowRef('app-a'), bizId: vue.shallowRef(11), traceId: vue.shallowRef('trace-a'), hasLlmTraces: vue.shallowRef(false), llmLoading: vue.shallowRef(true), traceLoading: vue.shallowRef(true) };
  const scope = vue.effectScope();
  return { context, scope, result: scope.run(() => useTracePanelPreference(context)) };
}

test('saved waterfall waits 500 ms then uses ready LLM without changing saved preference or switching back', async () => {
  const { context, result, scope } = createPreference();
  context.hasLlmTraces.value = true;
  context.llmLoading.value = false;
  await flush();
  await new Promise(resolve => setTimeout(resolve, 250));
  assert.equal(result.panel.value, 'timeline');
  await new Promise(resolve => setTimeout(resolve, 300));
  assert.equal(result.panel.value, 'llm');
  assert.equal(localStorage.getItem('trace_detail_panel:11:app-a'), 'timeline');
  context.traceLoading.value = false;
  await flush();
  assert.equal(result.panel.value, 'llm');
  scope.stop();
});

test('waterfall finishing within grace period cancels fallback, and manual selection wins', async () => {
  const { context, result, scope } = createPreference();
  context.hasLlmTraces.value = true;
  await flush();
  context.traceLoading.value = false;
  await flush();
  await new Promise(resolve => setTimeout(resolve, 550));
  assert.equal(result.panel.value, 'timeline');
  context.traceId.value = 'trace-b';
  context.traceLoading.value = true;
  await flush();
  result.selectPanel('topo');
  await new Promise(resolve => setTimeout(resolve, 550));
  assert.equal(result.panel.value, 'topo');
  scope.stop();
});

test('server preview objects retain KV values and JSON text is displayed without parsing', () => {
  const { buildIoPreviews } = sourceLoader()(path.join(root, 'inquire-content/llm-observation/utils/transform.ts'));
  const result = buildIoPreviews([{ trace_id: 'trace-a', flow: [{ span_id: 'tool-a', input: { path: 'a', count: '2' }, output: '{"literal":"text"}' }] }]);
  assert.deepEqual(result.get('trace-a:tool-a'), {
    input: [{ type: 'kv', pairs: [{ key: 'path', value: 'a' }, { key: 'count', value: '2' }] }],
    output: [{ type: 'text', text: '{"literal":"text"}' }],
  });
});

test('outer time metadata stays unavailable while Trace is pending, then accepts real zero duration', () => {
  const store = vue.reactive({ loading: true });
  const traceTree = vue.shallowRef({ spans: [] });
  const ready = loadFunction(path.join(root, 'inquire-content/trace-detail.tsx'), 'traceInfoReady', {
    computed: vue.computed, isLoading: vue.shallowRef(false), store, traceTree,
  });
  assert.equal(ready.value, false);
  store.loading = false;
  assert.equal(ready.value, false);
  traceTree.value = { spans: [{ duration: 0 }] };
  assert.equal(ready.value, true);
});
