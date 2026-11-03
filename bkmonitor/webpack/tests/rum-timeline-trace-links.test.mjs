import assert from 'node:assert/strict';
import fs from 'node:fs';
import { createRequire } from 'node:module';
import path from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';
import ts from 'typescript';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const vue = createRequire(path.join(root, 'src/trace/package.json'))('vue');
const base = 'src/trace/pages/rum-explore/detail/';
const flush = () => new Promise(resolve => setImmediate(resolve));
const traceId = index => index.toString(16).padStart(32, '0');
const trace = (index, applicationId = 1) => ({
  trace_id: traceId(index),
  application_id: applicationId,
  app_name: `app-${applicationId}`,
  app_alias: `应用-${applicationId}`,
  bk_biz_id: 2,
});

function harness(t) {
  const scope = vue.effectScope();
  const unmount = [];
  const timers = new Map();
  const requests = [];
  const scopeKey = vue.shallowRef('rum-app|view-a');
  const bizId = vue.shallowRef(2);
  let timerId = 0;
  const { useTimelineTraceLinks } = load(
    `${base}composables/use-timeline-trace-links.ts`,
    {
      vue: { ...vue, onBeforeUnmount: callback => unmount.push(callback) },
      '../services/trace-link': {
        streamTraceInfos: (ids, biz, onData, signal) =>
          new Promise(resolve => requests.push({ ids, biz, onData, signal, resolve })),
      },
    },
    {
      setTimeout: callback => {
        const id = ++timerId;
        timers.set(id, callback);
        return id;
      },
      clearTimeout: id => timers.delete(id),
    }
  );
  const state = scope.run(() => useTimelineTraceLinks(scopeKey, bizId));
  const dispose = () => {
    unmount.forEach(callback => callback());
    scope.stop();
  };
  t.after(dispose);
  return {
    ...state,
    scopeKey,
    bizId,
    timers,
    requests,
    dispose,
    tick() {
      assert.equal(timers.size, 1);
      const [id, callback] = timers.entries().next().value;
      timers.delete(id);
      callback();
    },
  };
}

function load(file, dependencies, globals = {}) {
  const compiled = ts.transpileModule(fs.readFileSync(path.join(root, file), 'utf8'), {
    fileName: file,
    reportDiagnostics: true,
    compilerOptions: {
      module: ts.ModuleKind.CommonJS,
      target: ts.ScriptTarget.ES2022,
      jsx: ts.JsxEmit.React,
      jsxFactory: 'h',
    },
  });
  assert.equal(compiled.diagnostics.length, 0, file);
  const exports = {};
  new Function('require', 'exports', 'h', ...Object.keys(globals), compiled.outputText)(
    id => {
      assert.ok(Object.hasOwn(dependencies, id), `Unexpected dependency: ${id}`);
      return dependencies[id];
    },
    exports,
    vue.h,
    ...Object.values(globals)
  );
  return exports;
}

test('visible TraceIDs are deduplicated into batches of at most 20 and results arrive before a batch ends', async t => {
  const state = harness(t);
  assert.equal(state.requests.length, 0);
  state.enqueueTraceIds(Array.from({ length: 23 }, (_, index) => traceId(index + 1)));
  state.enqueueTraceIds([traceId(1), traceId(2), '', 'invalid-trace-id']);
  assert.equal(state.requests.length, 0);
  state.tick();
  assert.deepEqual(
    state.requests[0].ids,
    Array.from({ length: 20 }, (_, index) => traceId(index + 1))
  );
  state.requests[0].onData([trace(1)]);
  assert.deepEqual(state.traceLinks.value.get(traceId(1)), [trace(1)]);
  assert.equal(state.requests.length, 1);
  state.requests[0].onData([trace(1), trace(1, 2), trace(2)]);
  assert.deepEqual(state.traceLinks.value.get(traceId(1)), [trace(1), trace(1, 2)]);
  assert.deepEqual(state.traceLinks.value.get(traceId(2)), [trace(2)]);
  state.requests[0].resolve();
  await flush();
  state.tick();
  assert.deepEqual(state.requests[1].ids, [traceId(21), traceId(22), traceId(23)]);
  state.requests[1].onData([trace(21, 3)]);
  assert.deepEqual(state.traceLinks.value.get(traceId(21)), [trace(21, 3)]);
  assert.deepEqual(state.traceLinks.value.get(traceId(1)), [trace(1), trace(1, 2)]);
  state.requests[1].resolve();
  await flush();
  state.enqueueTraceIds([traceId(1), traceId(23)]);
  assert.equal(state.timers.size, 0);
  assert.equal(state.requests.length, 2);
});

for (const field of ['scopeKey', 'bizId']) {
  test(`changing ${field} aborts the previous search and discards its late snapshots`, async t => {
    const state = harness(t);
    state.enqueueTraceIds([traceId(1), traceId(2)]);
    state.tick();
    const old = state.requests[0];
    old.onData([trace(1)]);
    state[field].value = field === 'bizId' ? 11 : 'rum-app|view-b';
    assert.equal(old.signal.aborted, true);
    assert.equal(state.traceLinks.value.size, 0);
    state.enqueueTraceIds([traceId(1)]);
    state.tick();
    const current = state.requests[1];
    assert.equal(current.biz, state.bizId.value);
    current.onData([trace(1, 3)]);
    old.onData([trace(1), trace(2)]);
    old.resolve();
    await flush();
    assert.deepEqual(state.traceLinks.value.get(traceId(1)), [trace(1, 3)]);
    assert.equal(state.traceLinks.value.has(traceId(2)), false);
    assert.equal(state.timers.size, 0);
  });
}

test('unmount cancels the active batch and prevents queued searches and late updates', async t => {
  const state = harness(t);
  state.enqueueTraceIds(Array.from({ length: 21 }, (_, index) => traceId(index + 1)));
  state.tick();
  const request = state.requests[0];
  state.dispose();
  assert.equal(request.signal.aborted, true);
  request.onData([trace(1)]);
  request.resolve();
  await flush();
  assert.equal(state.traceLinks.value.size, 0);
  assert.equal(state.timers.size, 0);
  assert.equal(state.requests.length, 1);
});

test('batch service reuses global SSE, forwards cancellation and publishes only Trace snapshots', async () => {
  const requests = [];
  const { streamTraceInfos, searchTraceInfo } = load(
    `${base}services/trace-link.ts`,
    {
      '@/utils': {
        fetchEventStream: async (url, options) => {
          requests.push({ url, options });
          options.onData({ type: 'apm_application', items: [{ app_name: 'unrelated' }] });
          options.onData({ type: 'trace', items: [trace(1)] });
          options.onData({ type: 'trace', items: [trace(1), trace(1, 2)] });
        },
      },
    },
    { location: { origin: 'https://monitor.example.com' }, window: { site_url: '/monitor/' } }
  );
  const snapshots = [];
  const abort = new AbortController();
  await streamTraceInfos([traceId(1), traceId(2)], 11, items => snapshots.push(items), abort.signal);
  const url = new URL(requests[0].url);
  assert.equal(url.pathname, '/monitor/rest/v2/overview/search/');
  assert.equal(url.searchParams.get('query'), `${traceId(1)},${traceId(2)}`);
  assert.equal(url.searchParams.get('bk_biz_id'), '11');
  assert.equal(requests[0].options.signal, abort.signal);
  assert.deepEqual(snapshots, [[trace(1)], [trace(1), trace(1, 2)]]);
  assert.deepEqual(await searchTraceInfo(traceId(1), 2), trace(1));
});

test('timeline rows preserve every linked TraceID without duplicating repeated links', () => {
  const { buildTimelineItems } = load(`${base}utils/timeline-transform.ts`, {
    dayjs: {},
    'monitor-common/utils/colorHelpers': { hexToRgba: color => color },
    '../../constants': { SPAN_TYPE_META: {} },
    '../composables/use-detail-sections': {},
    '../constants': { TIMELINE_HEAD_SIZE: 5 },
    '../registry/timeline-span-registry': { getTimelineSpanTypeConfig: () => ({}) },
    '../typings': {},
    '@/components/trace-view/utils/date': {},
  });
  const items = buildTimelineItems([{ span_id: 'resource-a' }], {
    recordMap: new Map([
      [
        'resource-a',
        {
          origin_data: {
            attributes: { span_type: 'resource' },
            links: [{ trace_id: traceId(1) }, { trace_id: traceId(2) }, { trace_id: traceId(1) }],
          },
        },
      ],
    ]),
    currentSpanId: '',
    currentPath: new Set(),
    expandedFolds: new Set(),
    expandedNodes: new Set(),
  });
  assert.equal(items.length, 1);
  assert.deepEqual(items[0].data.traceIds, [traceId(1), traceId(2)]);
});

test('only visible Resource rows enqueue their linked TraceIDs and clicking uses the selected application', () => {
  const row = load(`${base}components/trace-context/timeline-span-row.tsx`, {
    vue,
    'vue-i18n': { useI18n: () => ({ t: value => value }) },
    './timeline-span-row.scss': {},
  }).default;
  const emitted = [];
  const rowProps = {
    data: {
      spanId: 'resource-a',
      spanType: 'resource',
      traceIds: [traceId(1), traceId(2)],
      level: 0,
      tag: { bgColor: '#fff', label: 'Resource', icon: '' },
      isCurrent: false,
    },
    traces: [],
  };
  const renderRow = row.setup(rowProps, { emit: (...args) => emitted.push(args) });
  assert.equal(renderRow().children[1].children[0], null);
  rowProps.traces = [trace(1), trace(1, 2)];
  const resource = renderRow();
  assert.equal(resource.props['data-trace-ids'], `${traceId(1)},${traceId(2)}`);
  const links = resource.children[1].children[0].children;
  assert.equal(links.length, 2);
  for (const link of links) {
    assert.equal(link.children[0].props.class, 'icon-monitor icon-dingwei1');
    assert.equal(link.children[1], '关联 Trace');
    assert.equal(link.props.title, undefined);
  }
  links[1].props.onClick();
  assert.deepEqual(emitted, [['traceClick', trace(1, 2)]]);
  rowProps.data.spanType = 'action';
  assert.equal(renderRow().props['data-trace-ids'], undefined);

  const mounted = [];
  const unmount = [];
  const queued = [];
  const observed = [];
  const traceLinks = vue.shallowRef(new Map());
  let intersection;
  let disconnected = false;
  const element = { dataset: { traceIds: resource.props['data-trace-ids'] } };
  const panel = load(
    `${base}components/trace-context/trace-context-panel.tsx`,
    {
      vue: {
        ...vue,
        onMounted: callback => mounted.push(callback),
        onBeforeUnmount: callback => unmount.push(callback),
        watch: () => {},
      },
      'bkui-vue': { Exception: {} },
      'vue-i18n': { useI18n: () => ({ t: value => value }) },
      '../../composables/use-timeline-trace-links': {
        useTimelineTraceLinks: () => ({
          traceLinks,
          enqueueTraceIds: ids => queued.push(ids),
        }),
      },
      '../detail-sections/waterfall-chart': { default: { name: 'WaterfallChart' } },
      './timeline-fold-row': { default: { name: 'TimelineFoldRow' } },
      './timeline-span-row': { default: { name: 'TimelineSpanRow' } },
      './timeline-view-header': { default: { name: 'TimelineViewHeader' } },
      './trace-context-panel.scss': {},
    },
    {
      IntersectionObserver: class {
        constructor(callback) {
          intersection = callback;
        }
        observe(target) {
          observed.push(target);
        }
        unobserve(target) {
          assert.equal(target, element);
        }
        disconnect() {
          disconnected = true;
        }
      },
    }
  ).default;
  const renderPanel = panel.setup(
    { bizId: 2, scopeKey: 'app-a|view-a', items: [{ kind: 'span', data: rowProps.data }], view: { spanId: 'view-a' } },
    { emit() {} }
  );
  renderPanel().children[0].children[0].props.onToggle();
  assert.deepEqual(renderPanel().children[0].children[2].children[0].props.traces, []);
  traceLinks.value = new Map([[traceId(2), [trace(2)]]]);
  assert.deepEqual(renderPanel().children[0].children[2].children[0].props.traces, [trace(2)]);
  traceLinks.value = new Map([...traceLinks.value, [traceId(1), [trace(1)]]]);
  assert.deepEqual(renderPanel().children[0].children[2].children[0].props.traces, [trace(2), trace(1)]);
  renderPanel().ref.r({ querySelectorAll: () => [element], contains: target => target === element });
  mounted.forEach(callback => callback());
  assert.deepEqual(observed, [element]);
  intersection([{ target: element, isIntersecting: false }]);
  assert.deepEqual(queued, []);
  intersection([{ target: element, isIntersecting: true }]);
  assert.deepEqual(queued, [[traceId(1), traceId(2)]]);
  unmount.forEach(callback => callback());
  assert.equal(disconnected, true);
});
