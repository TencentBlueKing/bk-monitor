import assert from 'node:assert/strict';
import fs from 'node:fs';
import { createRequire } from 'node:module';
import path from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';
import ts from 'typescript';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const vue = createRequire(path.join(root, 'src/trace/package.json'))('vue');
const base = 'src/trace/pages/alarm-center/alarm-issues/';
const components = `${base}issues-detail/components/issues-ai-analysis/`;
const issueA = { bk_biz_id: 2, issue_id: 'issue-a' };
const issueB = { bk_biz_id: 2, issue_id: 'issue-b' };
const flush = () => new Promise(resolve => setImmediate(resolve));

function analysis(params, status = 'running') {
  return {
    is_repository_configured: true,
    is_configured: true,
    marker: `${params.bk_biz_id}:${params.issue_id}`,
    latest: { status, analysis_id: `analysis-${params.issue_id}` },
  };
}

function harness(t, { honorAbort = true } = {}) {
  const scope = vue.effectScope();
  const unmount = [];
  const beforeUnmount = [];
  const timers = new Map();
  const queries = [];
  const submissions = [];
  const messages = [];
  let timerId = 0;
  const lifecycleVue = {
    ...vue,
    onUnmounted: callback => unmount.push(callback),
    onBeforeUnmount: callback => beforeUnmount.push(callback),
  };
  const useRequestAbort = load('src/trace/hooks/useRequestAbort.ts', { vue: lifecycleVue }).default;
  const query =
    scene =>
    (params, { signal }) =>
      new Promise((resolve, reject) => {
        const request = {
          params,
          signal,
          scene,
          resolve: (status = 'running') => {
            const data = analysis(params, status);
            resolve(scene === 'overview' ? { source_analysis: data } : data);
          },
          reject,
        };
        queries.push(request);
        // The standard request layer strips ERR_CANCELED into an empty rejection.
        if (honorAbort) signal.addEventListener('abort', () => reject(''), { once: true });
      });
  const services = {
    getIssueAiAnalysisOverview: query('overview'),
    getIssueSourceAnalysis: query('view'),
    ...Object.fromEntries(
      ['start', 'retry', 'reanalyze'].map(kind => [
        `${kind}IssueSourceAnalysis`,
        params => new Promise((resolve, reject) => submissions.push({ kind, params, resolve, reject })),
      ])
    ),
  };
  const { useIssuesAiAnalysis } = load(
    `${base}composables/use-issues-ai-analysis.ts`,
    {
      vue: lifecycleVue,
      '@vueuse/core': {
        createGlobalState: factory => {
          let state;
          return () => (state ??= factory());
        },
      },
      'trace/common/message': { bkUiMessage: message => messages.push(message) },
      'vue-i18n': { useI18n: () => ({ t: value => value }) },
      '../services/issues-ai-analysis': services,
      '@/hooks/useRequestAbort': { default: useRequestAbort },
    },
    {
      setTimeout: (callback, delay) => {
        const id = ++timerId;
        timers.set(id, { callback, delay });
        return id;
      },
      clearTimeout: id => timers.delete(id),
    }
  );
  const state = scope.run(useIssuesAiAnalysis);
  const mount = (file, props, dependencies) => {
    const component = load(file, {
      vue: lifecycleVue,
      'vue-i18n': { useI18n: () => ({ t: value => value }) },
      '../../../composables/use-issues-ai-analysis': { useIssuesAiAnalysis },
      '../composables/use-issues-ai-analysis': { useIssuesAiAnalysis },
      ...dependencies,
    }).default;
    return scope.run(() => component.setup(props, { emit() {} }));
  };
  t.after(() => scope.stop());
  return {
    state,
    queries,
    submissions,
    timers,
    messages,
    unmount() {
      beforeUnmount.forEach(callback => callback());
      unmount.forEach(callback => callback());
    },
    tick() {
      assert.equal(timers.size, 1);
      const [id, { callback, delay }] = timers.entries().next().value;
      assert.equal(delay, 3000);
      timers.delete(id);
      callback();
    },
    overview(params = issueA) {
      const props = vue.reactive({ detail: { bk_biz_id: params.bk_biz_id, id: params.issue_id } });
      mount(`${components}issues-ai-analysis-overview.tsx`, props, {
        'bkui-vue': {},
        '../basic-card/basic-card': {},
        '@/static/img/issues/ai-analysis.svg': {},
        './issues-ai-analysis-overview.scss': {},
      });
      return props;
    },
    report() {
      const props = vue.reactive({ show: false, detail: { bk_biz_id: issueA.bk_biz_id, id: issueA.issue_id } });
      const firstHook = beforeUnmount.length;
      mount(`${components}source-code-analysis.tsx`, props, {
        'bkui-vue': {},
        'bkui-vue/lib/icon': {},
        dayjs: {},
        '../../../../../../components/markdown-editor/viewer': {},
        '../../../services/issues-operations': {},
        './analysis-summary-card': {},
        '@/static/img/issues/ai-analysis.svg': {},
        './source-code-analysis.scss': {},
      });
      return { props, unmount: () => beforeUnmount.slice(firstHook).forEach(callback => callback()) };
    },
    slider() {
      const props = vue.reactive({ show: true, issueBizId: issueA.bk_biz_id, issueId: issueA.issue_id });
      const refs = Object.fromEntries(
        ['bizId', 'issueId', 'detail', 'loading', 'error', 'timeRange', 'timezone', 'refreshInterval'].map(key => [
          key,
          vue.shallowRef(null),
        ])
      );
      const instance = mount(`${base}issues-detail/issues-detail-sideslider.tsx`, props, {
        'bkui-vue': {},
        'monitor-common/utils': {},
        'monitor-pc/i18n/dayjs': {},
        pinia: { storeToRefs: () => refs },
        'trace/components/retrieval-filter/query-string-utils': {},
        'trace/components/retrieval-filter/typing': { EMode: { ui: 'ui' } },
        '../../common-detail/detail-loading': {},
        '../components/issues-impact-scope-drawer/issues-impact-scope-drawer': {},
        './components/issues-loading': {},
        './components/issues-slider-header': {},
        './components/issues-slider-wrapper': {},
        '@/components/refresh-rate/refresh-rate': {},
        '@/components/retrieval-filter/utils': {},
        '@/components/time-range/time-range': {},
        '@/store/modules/issues-detail': {
          useIssuesDetailStore: () => ({ reset() {}, refresh() {}, fetchDetail() {} }),
        },
        './issues-detail-sideslider.scss': {},
      });
      return { props, instance };
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
  const module = { exports: {} };
  new Function('require', 'module', 'exports', ...Object.keys(globals), compiled.outputText)(
    id => {
      assert.ok(Object.hasOwn(dependencies, id), `Unexpected dependency: ${id}`);
      return dependencies[id];
    },
    module,
    module.exports,
    ...Object.values(globals)
  );
  return module.exports;
}

test('switching the overview from A to B cancels A without recreating its polling chain', async t => {
  const ctx = harness(t);
  const props = ctx.overview();
  ctx.queries[0].resolve();
  await flush();
  ctx.tick();
  const oldPoll = ctx.queries.at(-1);
  props.detail = { bk_biz_id: issueB.bk_biz_id, id: issueB.issue_id };
  await flush();
  assert.equal(oldPoll.signal.aborted, true);
  assert.equal(ctx.state.sourceAnalysisData.value, null);
  assert.equal(ctx.state.loading.sourceAnalysis, true);
  assert.equal(ctx.timers.size, 0);
  ctx.queries.at(-1).resolve();
  await flush();
  for (let i = 0; i < 3; i++) {
    ctx.tick();
    assert.deepEqual(ctx.queries.at(-1).params, issueB);
    ctx.queries.at(-1).resolve();
    await flush();
    assert.equal(ctx.state.sourceAnalysisData.value.marker, '2:issue-b');
  }
  assert.equal(ctx.timers.size, 1);
});

for (const outcome of ['resolve', 'reject']) {
  test(`late A ${outcome} cannot change B's data, loading or timer`, async t => {
    const ctx = harness(t, { honorAbort: false });
    const props = ctx.overview();
    const old = ctx.queries[0];
    props.detail = { bk_biz_id: issueB.bk_biz_id, id: issueB.issue_id };
    await flush();
    old[outcome]();
    await flush();
    assert.equal(ctx.state.loading.sourceAnalysis, true);
    assert.equal(ctx.state.sourceAnalysisData.value, null);
    assert.equal(ctx.timers.size, 0);
    ctx.queries.at(-1).resolve();
    await flush();
    assert.equal(ctx.state.sourceAnalysisData.value.marker, '2:issue-b');
    assert.equal(ctx.timers.size, 1);
  });
}

test('a stale success arriving after B succeeds cannot overwrite B or create a second timer', async t => {
  const ctx = harness(t, { honorAbort: false });
  const props = ctx.overview();
  const old = ctx.queries[0];
  props.detail = { bk_biz_id: issueB.bk_biz_id, id: issueB.issue_id };
  await flush();
  ctx.queries.at(-1).resolve();
  await flush();
  const timer = [...ctx.timers.keys()];
  old.resolve('success');
  await flush();
  assert.equal(ctx.state.sourceAnalysisData.value.marker, '2:issue-b');
  assert.equal(ctx.state.sourceAnalysisData.value.latest.status, 'running');
  assert.deepEqual([...ctx.timers.keys()], timer);
});

test('an already queued stale timer cannot cancel the current Issue polling', async t => {
  const ctx = harness(t);
  const props = ctx.overview();
  ctx.queries[0].resolve();
  await flush();
  const oldCallback = [...ctx.timers.values()][0].callback;
  props.detail = { bk_biz_id: issueB.bk_biz_id, id: issueB.issue_id };
  await flush();
  ctx.queries.at(-1).resolve();
  await flush();
  const timer = [...ctx.timers.keys()];
  oldCallback();
  assert.equal(ctx.queries.length, 2);
  assert.deepEqual([...ctx.timers.keys()], timer);
});

test('the request identity includes business ID even when the Issue ID is unchanged', async t => {
  const ctx = harness(t, { honorAbort: false });
  const props = ctx.overview();
  props.detail = { bk_biz_id: 7, id: issueA.issue_id };
  await flush();
  ctx.queries.at(-1).resolve();
  await flush();
  ctx.queries[0].resolve();
  await flush();
  assert.equal(ctx.state.sourceAnalysisData.value.marker, '7:issue-a');
  assert.equal(ctx.timers.size, 1);
});

test('A to B to A and overlapping same-Issue refreshes reject previous request generations', async t => {
  const ctx = harness(t, { honorAbort: false });
  const props = ctx.overview();
  props.detail = { bk_biz_id: issueB.bk_biz_id, id: issueB.issue_id };
  await flush();
  props.detail = { bk_biz_id: issueA.bk_biz_id, id: issueA.issue_id };
  await flush();
  const current = ctx.state.getSourceAnalysisData(issueA);
  ctx.queries.at(-1).resolve();
  await current;
  const timer = [...ctx.timers.keys()];
  for (const request of ctx.queries.slice(0, -1)) request.resolve('success');
  await flush();
  assert.equal(ctx.state.sourceAnalysisData.value.latest.status, 'running');
  assert.deepEqual([...ctx.timers.keys()], timer);
});

test('switching overview and full-report scenes aborts the other query and resumes overview polling', async t => {
  const ctx = harness(t, { honorAbort: false });
  ctx.overview();
  const { props: report } = ctx.report();
  const overview = ctx.queries[0];
  report.show = true;
  await flush();
  const fullReport = ctx.queries.at(-1);
  assert.equal(fullReport.scene, 'view');
  assert.equal(overview.signal.aborted, true);
  fullReport.resolve();
  await flush();
  overview.resolve('success');
  await flush();
  assert.equal(ctx.state.sourceAnalysisData.value.latest.status, 'running');
  ctx.tick();
  const oldReport = ctx.queries.at(-1);
  report.show = false;
  await flush();
  assert.equal(oldReport.signal.aborted, true);
  assert.equal(ctx.queries.at(-1).scene, 'overview');
  ctx.queries.at(-1).resolve();
  await flush();
  oldReport.resolve('success');
  await flush();
  assert.equal(ctx.state.sourceAnalysisData.value.latest.status, 'running');
  ctx.tick();
  assert.equal(ctx.queries.at(-1).scene, 'overview');
});

test('unmounting the full-report component resumes the overview without reviving its old query', async t => {
  const ctx = harness(t, { honorAbort: false });
  ctx.overview();
  const report = ctx.report();
  report.props.show = true;
  await flush();
  const old = ctx.queries.at(-1);
  report.unmount();
  const overview = ctx.queries.at(-1);
  assert.equal(old.signal.aborted, true);
  assert.equal(overview.scene, 'overview');
  overview.resolve();
  await flush();
  old.resolve('success');
  await flush();
  assert.equal(ctx.state.sourceAnalysisData.value.latest.status, 'running');
  ctx.tick();
  assert.equal(ctx.queries.at(-1).scene, 'overview');
});

test('unmounting the full report after closing the side-slider does not restart polling', async t => {
  const ctx = harness(t, { honorAbort: false });
  const slider = ctx.slider();
  ctx.overview();
  const report = ctx.report();
  report.props.show = true;
  await flush();
  const count = ctx.queries.length;
  slider.instance.handleShowChange(false);
  report.unmount();
  for (const request of ctx.queries) request.resolve();
  await flush();
  assert.equal(ctx.queries.length, count);
  assert.equal(ctx.state.sourceAnalysisData.value, null);
  assert.equal(ctx.timers.size, 0);
});

test('a current polling error preserves pending data and retries; terminal success stops polling', async t => {
  const ctx = harness(t);
  ctx.overview();
  ctx.queries[0].resolve();
  await flush();
  ctx.tick();
  ctx.queries.at(-1).reject('');
  await flush();
  assert.equal(ctx.state.sourceAnalysisData.value.latest.status, 'running');
  assert.equal(ctx.state.loading.sourceAnalysis, false);
  ctx.tick();
  ctx.queries.at(-1).resolve('success');
  await flush();
  assert.equal(ctx.timers.size, 0);
  assert.equal(ctx.state.sourceAnalysisData.value.latest.status, 'success');
});

for (const action of ['switch', 'close', 'external-close', 'unmount']) {
  test(`side-slider ${action} invalidates pending analysis before another detail arrives`, async t => {
    const ctx = harness(t, { honorAbort: false });
    const slider = ctx.slider();
    ctx.overview();
    const old = ctx.queries[0];
    if (action === 'switch') slider.props.issueId = issueB.issue_id;
    if (action === 'close') slider.instance.handleShowChange(false);
    if (action === 'external-close') slider.props.show = false;
    if (action === 'unmount') ctx.unmount();
    await flush();
    assert.equal(old.signal.aborted, true);
    old.resolve();
    await flush();
    assert.equal(ctx.state.sourceAnalysisData.value, null);
    assert.equal(ctx.state.loading.sourceAnalysis, false);
    assert.equal(ctx.timers.size, 0);
  });
}

test('clear aborts both request hooks and prevents timer resurrection after reopening the same Issue', async t => {
  const ctx = harness(t, { honorAbort: false });
  const overview = ctx.state.getSourceAnalysisData(issueA);
  ctx.state.sourceAnalysisScene.value = 'view';
  const report = ctx.state.getSourceAnalysisData(issueA);
  ctx.state.clearSetTimeout();
  assert.ok(ctx.queries.every(request => request.signal.aborted));
  ctx.state.sourceAnalysisScene.value = 'overview';
  const reopened = ctx.state.getSourceAnalysisData(issueA);
  ctx.queries[2].resolve();
  await reopened;
  const timer = [...ctx.timers.keys()];
  ctx.queries[0].resolve('success');
  ctx.queries[1].resolve('success');
  await Promise.all([overview, report]);
  assert.equal(ctx.state.sourceAnalysisData.value.latest.status, 'running');
  assert.deepEqual([...ctx.timers.keys()], timer);
});

for (const kind of ['start', 'retry', 'reanalyze']) {
  test(`late ${kind} submission for A cannot overwrite B or clear B's submission loading`, async t => {
    const ctx = harness(t);
    const props = ctx.overview();
    ctx.queries[0].resolve(kind === 'retry' ? 'failed' : 'success');
    await flush();
    const submit = params =>
      kind === 'start'
        ? ctx.state.handleStartAnalysis(params)
        : ctx.state.handleReanalyzeSourceAnalysis({ ...params, analysis_id: `analysis-${params.issue_id}` });
    const old = submit(issueA);
    props.detail = { bk_biz_id: issueB.bk_biz_id, id: issueB.issue_id };
    await flush();
    ctx.queries.at(-1).resolve(kind === 'retry' ? 'failed' : 'success');
    await flush();
    const current = submit(issueB);
    assert.equal(ctx.submissions.length, 2);
    assert.equal(ctx.submissions[0].kind, kind);
    ctx.submissions[0].resolve(analysis(issueA, 'pending'));
    await old;
    assert.equal(ctx.state.sourceAnalysisData.value.marker, '2:issue-b');
    assert.equal(ctx.state.loading.retryAnalysis, true);
    assert.equal(ctx.queries.length, 2);
    assert.equal(ctx.messages.length, 0);
    ctx.submissions[1].resolve(analysis(issueB, 'success'));
    await current;
    assert.equal(ctx.state.loading.retryAnalysis, false);
  });
}
