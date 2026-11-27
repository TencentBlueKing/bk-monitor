const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const ts = require('typescript');

const root = path.join(__dirname, '../src/monitor-pc');
const favorite = 'pages/data-retrieval/favorite-container/component';
const report = 'pages/email-subscriptions';
const space = id => ({ id, bk_biz_id: id, space_name: String(id), text: String(id), py_text: String(id) });

function load(file, window, dependencies = {}) {
  let source = fs.readFileSync(path.join(root, file), 'utf8');
  if (file.endsWith('.vue')) source = source.match(/<script[^>]*>([\s\S]*?)<\/script>/)[1];
  const { outputText } = ts.transpileModule(source, {
    fileName: file.replace(/\.vue$/, '.ts'),
    compilerOptions: {
      module: ts.ModuleKind.CommonJS,
      target: ts.ScriptTarget.ES2022,
      experimentalDecorators: true,
      jsx: ts.JsxEmit.React,
      jsxFactory: 'h',
    },
  });
  const noopDecorator = () => () => {};
  const Base = class {};
  const component = value => typeof value === 'function' ? value : constructor => constructor;
  const mocks = {
    'vue-property-decorator': { Component: component, Vue: Base, Emit: noopDecorator, Watch: noopDecorator,
      Prop: noopDecorator, Ref: noopDecorator, Model: noopDecorator },
    'vue-tsx-support': { Component: Base },
    'monitor-common/utils/utils': { deepClone: structuredClone, Debounce: noopDecorator },
    ...dependencies,
  };
  const exports = {};
  const h = (tag, props, ...children) => ({ tag, props, children });
  new Function('require', 'exports', 'window', 'h', outputText)(id => mocks[id] || {}, exports, window, h);
  return exports;
}

function setup() {
  const window = { space_list_state: 'deferred', cc_biz_id: 2, i18n: { t: text => text } };
  const getters = { bizId: 2, bizList: [space(2)], get bizIdMap() { return new Map(this.bizList.map(item => [item.id, item])); } };
  const sent = [];
  const messages = [];
  const { splitGraphId } = load(report + '/utils.ts', window);
  const Chart = load(report + '/components/select-chart.vue', window, {
    '../utils': { splitGraphId }, './store': { defaultRadioList: [] },
    'monitor-api/modules/grafana': { getDashboardList: async () => [] },
    'monitor-api/modules/report': { buildInMetric: async () => [{ uid: 'built-in' }] },
  }).default;
  const Share = load(favorite + '/shared-dialog.tsx', window, {
    'monitor-api/modules/model': { shareFavorite: async data => sent.push(data) },
  }).default;
  const share = Object.assign(new Share(), {
    $store: { getters }, listRef: { selectList: ['*'] }, favoriteConfig: { name: 'example', config: {} },
    $bkMessage: ({ message }) => messages.push(message), $t: key => key,
  });
  const chart = Object.assign(new Chart(), { $store: { getters } });
  const full = (...ids) => {
    getters.bizList = ids.map(space);
    window.space_list_state = 'full';
  };
  return { window, getters, chart, share, full, sent, messages };
}

test('a saved dashboard chart in another space opens the same tab before and after directory hydration', async () => {
  const { chart, full } = setup();
  await chart.created();
  for (const ready of [false, true]) {
    if (ready) full(2, 7, -9);
    chart.selectedActive = '';
    chart.handleSelectItem({ id: '7-dash-one-1' });
    assert.equal(chart.tool.active, 'grafana');
    assert.equal(chart.curBizId, '7');
    assert.equal(chart.leftActive, 'dash-one');
    chart.handleSelectItem({ id: '-9-dash-two-3' });
    assert.equal(chart.tool.active, 'grafana');
    assert.equal(chart.curBizId, '-9');
    for (const scope of ['7', '2,-9', 'all', 'notify']) {
      chart.handleSelectItem({ id: scope + '-built-in-4' });
      assert.equal(chart.tool.active, 'default');
      assert.deepEqual(chart.DefaultCurBizIdList, scope.split(','));
      assert.equal(chart.leftActive, 'built-in');
    }
  }
});

test('full-screen report content resolves space names from the current directory', () => {
  const { window, getters, full } = setup();
  const Content = load(report + '/components/subscription-content.tsx', window).default;
  const vm = Object.assign(new Content(), { $store: { getters } });
  assert.equal(vm.getBizName('7'), '--');
  full(2, 7);
  assert.equal(vm.getBizName('7'), '7');
});

test('an uptime node in another space gains its ownership label when the directory arrives', () => {
  const { window, getters, full } = setup();
  const editor = load('pages/uptime-check/uptime-check-nodes/uptime-check-node-edit.vue', window, {
    '../../../mixins/authorityMixin': { default: () => ({}) },
  }).default;
  const vm = { $store: { getters }, $t: key => key };
  const state = editor.data.call(vm);
  const options = () => editor.computed.businessList?.call(vm) ?? state.businessList;
  assert.deepEqual(options().map(space => space.id), [2]);
  full(2, 7);
  assert.equal(options().find(space => space.id === 7)?.text, '7');
});

test('sharing all waits for the full scope; explicitly selected IDs remain usable', async () => {
  const { share, sent, messages, full, window } = setup();
  function listProps(node) {
    if (node?.props?.ref === 'list') return node.props;
    return node?.children?.map(listProps).find(Boolean);
  }
  assert.equal(listProps(share.render()).allowSelectAll, false);
  await share.handleSubmitFormData();
  assert.equal(sent.length, 0);
  assert.equal(messages.length, 1);
  share.listRef.selectList = [2];
  await share.handleSubmitFormData();
  assert.deepEqual(sent[0].share_bk_biz_ids, [2]);
  full(2, 7);
  assert.equal(listProps(share.render()).allowSelectAll, true);
  share.listRef.selectList = ['*'];
  await share.handleSubmitFormData();
  assert.deepEqual(sent[1].share_bk_biz_ids, [2, 7]);
  delete window.space_list_state;
  assert.equal(listProps(share.render()).allowSelectAll, true);
});

test('share-all retains the 500 filtered-space limit, including a search beyond the first 500', async () => {
  const { share, full, sent } = setup();
  full(...Array.from({ length: 502 }, (_, i) => i + 1));
  await share.handleSubmitFormData();
  assert.deepEqual(sent[0].share_bk_biz_ids, Array.from({ length: 500 }, (_, i) => i + 1));
  share.keyword = '502';
  await share.handleSubmitFormData();
  assert.deepEqual(sent[1].share_bk_biz_ids, [502]);
  share.keyword = 'absent';
  await share.handleSubmitFormData();
  assert.equal(sent.length, 2);
});
