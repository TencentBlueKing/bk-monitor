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
const params = { bk_biz_id: 2, issue_id: 'issue-a' };
const i18n = { useI18n: () => ({ t: value => value }) };
const h = (type, props, ...children) => ({ type, props: props || {}, children: children.flat(Infinity) });
const nodes = tree => (tree && typeof tree === 'object' ? [tree, ...(tree.children || []).flatMap(nodes)] : []);
const buttons = tree => nodes(tree).filter(node => node.type === 'Button' && node.children.includes('重新分析'));

function analysis(status = 'success') {
  return {
    is_repository_configured: true,
    is_configured: true,
    latest: {
      analysis_id: 'analysis-a',
      status,
      failure: { message: 'pipeline failed' },
      result: { result_type: 'HIGH_CONFIDENCE', result_card: { description: 'old report', responsibility: {} } },
    },
  };
}

function harness({ status = 'success', submit = async () => analysis('pending'), query } = {}) {
  const messages = [];
  const calls = [];
  const queries = [];
  const timers = new Map();
  let timerId = 0;
  const { transformMessageProps } = load('src/monitor-pc/common/transform-message-props.ts', {});
  const message = load('src/trace/common/message.ts', {
    'bkui-vue': { Message: options => messages.push(options) },
    'monitor-pc/common/transform-message-props': { transformMessageProps },
  });
  const services = {
    getIssueAiAnalysisOverview: async values => {
      queries.push(['overview', values]);
      return { source_analysis: await (query ? query() : analysis('pending')) };
    },
    getIssueSourceAnalysis: async values => {
      queries.push(['view', values]);
      return query ? query() : analysis('pending');
    },
    ...Object.fromEntries(
      ['retry', 'reanalyze'].map(kind => [
        `${kind}IssueSourceAnalysis`,
        (...args) => {
          calls.push({ kind, args });
          return submit(...args);
        },
      ])
    ),
  };
  const { useIssuesAiAnalysis } = load(
    `${base}composables/use-issues-ai-analysis.ts`,
    {
      vue,
      '@vueuse/core': { createGlobalState: factory => factory },
      'trace/common/message': message,
      'vue-i18n': i18n,
      '../services/issues-ai-analysis': services,
      '@/hooks/useRequestAbort': { default: run => ({ run, signal: { aborted: false } }) },
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
  const state = useIssuesAiAnalysis();
  const previous = analysis(status);
  state.sourceAnalysisData.value = previous;
  return { state, previous, messages, calls, queries, timers };
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
  new Function('require', 'module', 'exports', 'h', ...Object.keys(globals), compiled.outputText)(
    id => {
      assert.ok(Object.hasOwn(dependencies, id), `Unexpected dependency: ${id}`);
      return dependencies[id];
    },
    module,
    module.exports,
    h,
    ...Object.values(globals)
  );
  return module.exports;
}

function overview(state) {
  const component = load(`${components}issues-ai-analysis-overview.tsx`, {
    vue: { ...vue, watch() {} },
    'bkui-vue': { Button: 'Button', Loading: 'Loading', Exception: 'Exception' },
    'vue-i18n': i18n,
    '../../../composables/use-issues-ai-analysis': { useIssuesAiAnalysis: () => state },
    '../basic-card/basic-card': {},
    '@/static/img/issues/ai-analysis.svg': {},
    './issues-ai-analysis-overview.scss': {},
  }).default;
  return component.setup({ detail: { bk_biz_id: params.bk_biz_id, id: params.issue_id } }, { emit() {} });
}

for (const status of ['success', 'failed']) {
  test(`${status}: accepted submission shows feedback and keeps polling`, async () => {
    const ctx = harness({ status });
    const input = status === 'failed' ? { ...params, analysis_id: 'analysis-a' } : params;
    await ctx.state.handleReanalyzeSourceAnalysis(input);
    assert.deepEqual(ctx.calls, [
      { kind: status === 'failed' ? 'retry' : 'reanalyze', args: [input, { needMessage: false }] },
    ]);
    assert.equal(ctx.messages.length, 1);
    assert.equal(ctx.messages[0].theme, 'success');
    assert.equal(ctx.messages[0].message, '分析任务已提交');
    assert.equal(ctx.state.sourceAnalysisData.value.latest.status, 'pending');
    assert.deepEqual(ctx.queries, [['overview', params]]);
    assert.equal([...ctx.timers.values()][0].delay, 3000);
    assert.equal(ctx.state.loading.retryAnalysis, false);
  });

  test(`${status}: overview disables and loads during submission; duplicate clicks do not submit`, async () => {
    let resolve;
    const ctx = harness({
      status,
      submit: () =>
        new Promise(yes => {
          resolve = yes;
        }),
    });
    const card = overview(ctx.state);
    let button = buttons(card.renderSourceCodeAnalysisView())[0];
    assert.equal(button.props.disabled, false);
    button.props.onClick();
    button = buttons(card.renderSourceCodeAnalysisView())[0];
    assert.equal(button.props.loading, true);
    assert.equal(button.props.disabled, true);
    button.props.onClick();
    assert.equal(ctx.calls.length, 1);
    assert.equal(ctx.state.sourceAnalysisData.value, ctx.previous);
    assert.equal(ctx.messages.length, 0);
    resolve(analysis('pending'));
    await new Promise(yes => setImmediate(yes));
    assert.equal(ctx.state.loading.retryAnalysis, false);
    assert.equal(buttons(card.renderSourceCodeAnalysisView()).length, 0);
  });
}

const details = { code: 3327002, overview: '上游服务不可用', popup_message: 'warning', trace_id: 'trace-a' };
for (const [name, error, expected] of [
  ['business error', { error_details: details, message: 'generic' }, '上游服务不可用'],
  ['HTTP error', { data: { error_details: details } }, '上游服务不可用'],
  ['plain backend error', { message: '用户无权限' }, '用户无权限'],
  ['structured message', { message: details }, '上游服务不可用'],
  ['network or timeout', '', '重新分析失败，请稍后重试'],
]) {
  test(`${name}: shows one error, preserves report and allows another attempt`, async () => {
    let fail = true;
    const ctx = harness({
      submit: async () => {
        if (fail) throw error;
        return analysis('pending');
      },
    });
    await ctx.state.handleReanalyzeSourceAnalysis(params);
    assert.equal(ctx.messages.length, 1);
    const message = ctx.messages[0].message;
    assert.equal(typeof message === 'string' ? message : message.overview, expected);
    if (typeof message === 'object') {
      assert.equal(JSON.parse(message.details).trace_id, 'trace-a');
      assert.equal(ctx.messages[0].theme, 'warning');
    }
    assert.equal(ctx.state.sourceAnalysisData.value, ctx.previous);
    assert.equal(ctx.state.loading.retryAnalysis, false);
    assert.equal(ctx.queries.length, 0);
    assert.equal(buttons(overview(ctx.state).renderSourceCodeAnalysisView())[0].props.disabled, false);
    fail = false;
    await ctx.state.handleReanalyzeSourceAnalysis(params);
    assert.equal(ctx.calls.length, 2);
    assert.equal(ctx.messages.at(-1).theme, 'success');
  });
}

test('failed retry submission preserves the previous failure and analysis ID', async () => {
  const ctx = harness({
    status: 'failed',
    submit: async () => {
      throw new Error('retry failed');
    },
  });
  const card = overview(ctx.state);
  await buttons(card.renderSourceCodeAnalysisView())[0].props.onClick();
  await new Promise(yes => setImmediate(yes));
  assert.equal(ctx.calls[0].kind, 'retry');
  assert.equal(ctx.calls[0].args[0].analysis_id, 'analysis-a');
  assert.equal(ctx.state.sourceAnalysisData.value, ctx.previous);
  assert.equal(ctx.messages[0].message, 'retry failed');
  assert.equal(ctx.state.loading.retryAnalysis, false);
});

test('full-report scene refreshes and polls the full report after acceptance', async () => {
  const ctx = harness();
  ctx.state.sourceAnalysisScene.value = 'view';
  await ctx.state.handleReanalyzeSourceAnalysis(params);
  assert.deepEqual(ctx.queries, [['view', params]]);
  assert.equal(ctx.timers.size, 1);
  ctx.state.clearSetTimeout();
  assert.equal(ctx.timers.size, 0);
});

test('status refresh failure after acceptance does not report submission failure or lose pending status', async () => {
  const ctx = harness({
    query: async () => {
      throw new Error('status unavailable');
    },
  });
  await ctx.state.handleReanalyzeSourceAnalysis(params);
  assert.equal(ctx.messages.length, 1);
  assert.equal(ctx.messages[0].theme, 'success');
  assert.equal(ctx.state.sourceAnalysisData.value.latest.status, 'pending');
  assert.equal(ctx.timers.size, 1);
  assert.equal(ctx.state.loading.retryAnalysis, false);
});

function summaryCard(props) {
  const component = load(
    `${components}analysis-summary-card.tsx`,
    {
      vue,
      'bkui-vue': { Button: 'Button', Progress: 'Progress', PopConfirm: 'PopConfirm' },
      'vue-i18n': i18n,
      dayjs: { default: { tz: () => ({ format: () => '' }) } },
      './analysis-summary-card.scss': {},
    },
    { window: { timezone: 'UTC' } }
  ).default;
  const state = component.setup(props);
  return component.render.call(vue.proxyRefs({ ...props, ...state, $emit() {} }));
}

test('full-report summary uses the same loading and disabled state', () => {
  const button = buttons(summaryCard({ sourceAnalysisData: analysis(), loading: { retryAnalysis: true } }))[0];
  assert.equal(button.props.disabled, true);
  assert.equal(button.props.loading, true);
});

for (const resultType of ['HIGH_CONFIDENCE', 'INSUFFICIENT_EVIDENCE']) {
  test(`${resultType}: null responsibility renders the report without assignment controls`, () => {
    const data = analysis();
    data.latest.result.result_type = resultType;
    data.latest.result.result_card.responsibility = null;
    const tree = summaryCard({ sourceAnalysisData: data, loading: { retryAnalysis: false } });
    assert.ok(nodes(tree).some(node => node.children.includes('old report')));
    assert.equal(buttons(tree).length, 1);
    assert.equal(nodes(tree).filter(node => node.type === 'PopConfirm').length, 0);
  });
}

test('full-report summary preserves assignment controls when responsibility has a user', () => {
  const data = analysis();
  data.latest.result.result_card.responsibility = { bk_username: 'review-user' };
  const tree = summaryCard({ sourceAnalysisData: data, loading: { retryAnalysis: false } });
  assert.equal(nodes(tree).filter(node => node.type === 'PopConfirm').length, 1);
});

test('service wrappers forward the standard request configuration to both APIs', async () => {
  const calls = [];
  const services = load(`${base}services/issues-ai-analysis.ts`, {
    'monitor-api/modules/issue': Object.fromEntries(
      ['retrySourceAnalysis', 'reanalyzeSourceAnalysis'].map(name => [
        name,
        (...args) => {
          calls.push({ name, args });
          return Promise.resolve(analysis('pending'));
        },
      ])
    ),
  });
  const options = { needMessage: false };
  await services.retryIssueSourceAnalysis({ ...params, analysis_id: 'analysis-a' }, options);
  await services.reanalyzeIssueSourceAnalysis(params, options);
  assert.equal(calls.length, 2);
  assert.ok(calls.every(call => call.args[1] === options));
});
