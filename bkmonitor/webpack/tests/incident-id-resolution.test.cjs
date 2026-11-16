const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const ts = require('typescript');

const source = fs.readFileSync(path.join(__dirname, '../src/trace/pages/failure/failure.tsx'), 'utf8');
const code = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, jsx: ts.JsxEmit.React, jsxFactory: 'h' },
}).outputText;

function mountPage(id, lookup) {
  const mounted = [];
  const calls = { lookup: [], routes: [], detail: [], results: [] };
  const ref = value => ({ value });
  const route = { name: 'incident-detail', params: { id }, query: { from: 'now-7d', activeTab: 'FailureTopo' } };
  const t = (message, params = {}) => message.replace(/\{(\w+)\}/g, (_, key) => params[key]);
  const mocks = {
    vue: {
      ref, shallowRef: ref, computed: getter => ({ get value() { return getter(); } }),
      defineComponent: value => value, provide: () => {}, watch: () => {},
      nextTick: callback => Promise.resolve().then(callback),
      onMounted: callback => mounted.push(callback), onBeforeUnmount: () => {},
    },
    'bkui-vue': { Exception: 'Exception', Loading: 'Loading', ResizeLayout: 'ResizeLayout' },
    'vue-i18n': { useI18n: () => ({ t }) },
    'vue-router': { useRoute: () => route, useRouter: () => ({ replace: async value => calls.routes.push(value) }) },
    'monitor-common/utils': { docCookies: { getItem: () => 'zhCN' }, LANGUAGE_COOKIE_KEY: 'language' },
    'monitor-api/modules/incident': {
      getIncidentDocId: params => { calls.lookup.push(params); return Promise.resolve().then(lookup); },
      incidentDetail: params => { calls.detail.push(params); return new Promise(() => {}); },
      incidentResults: params => { calls.results.push(params); return new Promise(() => {}); },
    },
    'monitor-api/modules/alert': {},
    './utils': { useIncidentProvider: () => {} },
    './composables/use-alarm-detail': { useIncidentAlarmDetail: () => ({}) },
    './failure-process/process': {},
    dayjs: () => {},
  };
  const module = { exports: {} };
  const load = name => {
    if (name in mocks) return mocks[name];
    if (name.startsWith('.')) return { default: name };
    throw new Error(`Unexpected import: ${name}`);
  };
  const h = (tag, props, ...children) => ({ tag, props, children });
  new Function('require', 'module', 'exports', 'window', 'h', code)(load, module, module.exports, { i18n: { t } }, h);
  const component = module.exports.default;
  const state = component.setup({ id });
  const render = () => component.render.call(Object.fromEntries(Object.entries(state).map(([key, value]) => [
    key, value && typeof value === 'object' && 'value' in value ? value.value : value,
  ])));
  return { calls, state, render, finish: async () => { for (const callback of mounted) await callback(); } };
}

for (const response of [{}, null, { id: '' }, { id: null }, { id: 0 }, { id: 'bad-id' }]) {
  test(`missing or invalid document ID blocks details and preserves the original URL: ${JSON.stringify(response)}`, async () => {
    const page = mountPage('123456', () => response);
    assert.equal(page.render().children[0].tag, 'Loading');
    await page.finish();
    assert.equal(page.calls.routes.length, 0);
    assert.deepEqual(page.calls.detail, []);
    assert.deepEqual(page.calls.results, []);
    assert.match(page.state.idResolveError.value, /123456/);
    assert.equal(page.render().children[0].tag, 'Exception');
    assert.equal(page.render().children[0].children[0].props.role, 'alert');
    page.state.getIncidentDetail();
    assert.deepEqual(page.calls.detail, []);
  });
}

test('lookup rejection stops detail requests and displays a retry message', async () => {
  const page = mountPage('123456', () => { throw new Error('lookup unavailable'); });
  await page.finish();
  assert.equal(page.calls.routes.length, 0);
  assert.deepEqual(page.calls.detail, []);
  assert.deepEqual(page.calls.results, []);
  assert.match(page.state.idResolveError.value, /刷新重试/);
});

test('valid conversion preserves query parameters and starts requests with the document ID', async () => {
  const documentId = '1793790000123456';
  const page = mountPage('123456', () => ({ id: documentId }));
  await page.finish();
  assert.deepEqual(page.calls.routes, [{ name: 'incident-detail', params: { id: documentId }, query: { from: 'now-7d', activeTab: 'FailureTopo' } }]);
  assert.deepEqual(page.calls.detail, [{ id: documentId }]);
  assert.deepEqual(page.calls.results, [{ id: documentId }]);
  assert.equal(page.state.idResolveError.value, '');
});

test('full document IDs bypass lookup and remain usable', async () => {
  const id = '1793790000123456';
  const page = mountPage(id, () => { throw new Error('must not resolve'); });
  await page.finish();
  assert.deepEqual(page.calls.lookup, []);
  assert.deepEqual(page.calls.routes, []);
  assert.deepEqual(page.calls.detail, [{ id }]);
  assert.deepEqual(page.calls.results, [{ id }]);
});

test('missing route ID shows an explicit error without issuing any request', async () => {
  const page = mountPage('', () => { throw new Error('must not resolve'); });
  await page.finish();
  assert.deepEqual(page.calls.lookup, []);
  assert.deepEqual(page.calls.detail, []);
  assert.deepEqual(page.calls.results, []);
  assert.match(page.state.idResolveError.value, /缺少故障 ID/);
  assert.equal(page.render().children[0].tag, 'Exception');
});
