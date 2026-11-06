const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const ts = require('typescript');
const Vue = require('vue');
const compiler = require('vue/compiler-sfc');

const root = path.join(__dirname, '../src/monitor-pc/pages/strategy-config/strategy-config-set');
const previewFile = 'strategy-template-preview/strategy-template-preview.vue';
const contentFile = 'strategy-template-preview/preview-template.vue';
const variablesFile = 'strategy-variate-list/strategy-variate-list.vue';
const flush = () => new Promise(resolve => setImmediate(resolve));
const sample = message => [{ type: 'weixin', label: 'WeChat', messages: [{ name: 'single', message, error: '' }] }];
const namedOutputConfig = {
  response_contract: 'named_outputs/v1',
  legacy_output_ref: 'RESULT',
  output_list: [{ reference_name: 'A', expression: 'a' }, { reference_name: 'RESULT', expression: 'a+b' }],
};

function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((onResolve, onReject) => {
    resolve = onResolve;
    reject = onReject;
  });
  return { promise, resolve, reject };
}

function descriptor(file) {
  const filename = path.join(root, file);
  const parsed = compiler.parse({ source: fs.readFileSync(filename, 'utf8'), filename });
  assert.deepEqual(parsed.errors, []);
  return parsed;
}

function loadComponent(file, request = async () => sample('example')) {
  const parsed = descriptor(file);
  const code = ts.transpileModule(parsed.script.content, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  }).outputText;
  const module = { exports: {} };
  const load = id => {
    if (id === 'monitor-api/modules/action') return { renderNoticeTemplate: request };
    if (id === 'monitor-common/utils/xss') return { sanitizeMailHtml: value => `sanitized:${value}` };
    if (id === 'vuex') {
      return { createNamespacedHelpers: () => ({ mapActions: () => ({ getRenderNoticeTemplate: request }) }) };
    }
    if (id === 'monitor-ui/monitor-dialog/monitor-dialog' || id === './preview-template') return {};
    throw new Error(`Unexpected import: ${id}`);
  };
  new Function('require', 'module', 'exports', code)(load, module, module.exports);
  const template = compiler.compileTemplate({ source: parsed.template.content, filename: parsed.filename });
  assert.deepEqual(template.errors, []);
  const render = new Function(`${template.code}; return { render, staticRenderFns };`)();
  return { ...module.exports.default, ...render };
}

function preview(request, props = {}) {
  const component = loadComponent(previewFile, request);
  return new Vue({
    ...component,
    propsData: { dialogShow: false, template: 'A', ...props },
    methods: { ...component.methods, $t: value => value },
  });
}

function allNodes(node) {
  if (!node) return [];
  return [node, ...(node.children || node.componentOptions?.children || []).flatMap(allNodes)];
}

function text(node) {
  return allNodes(node).map(value => value.text || '').join('');
}

test('preview caches only completed requests and reuses the same successful template', async () => {
  const response = deferred();
  const calls = [];
  const vm = preview(params => { calls.push(params); return response.promise; });
  vm.dialogShow = true;
  await Vue.nextTick();
  assert.deepEqual(calls, [{ template: 'A' }]);
  assert.equal(vm.loading, true);
  assert.equal(vm.oldTemplate, '');
  response.resolve(sample('rendered A'));
  await flush();
  assert.equal(vm.oldTemplate, 'A');
  assert.equal(vm.renderData[0].messages[0].message, 'rendered A');
  assert.equal(vm.loading, false);
  vm.dialogShow = false;
  await Vue.nextTick();
  vm.dialogShow = true;
  await flush();
  assert.equal(calls.length, 1);
  vm.$destroy();
});

test('request failure clears previous results and reopening retries the same template', async () => {
  const responses = [deferred(), deferred()];
  let calls = 0;
  const vm = preview(() => responses[calls++].promise);
  vm.renderData = sample('stale result');
  vm.dialogShow = true;
  await Vue.nextTick();
  assert.equal(vm.renderData.length, 0);
  responses[0].reject({ message: 'upstream failed', error_details: 'specific failure' });
  await flush();
  assert.equal(vm.renderData.length, 0);
  assert.equal(vm.previewError, 'specific failure');
  assert.equal(vm.oldTemplate, '');
  assert.equal(vm.loading, false);
  vm.dialogShow = false;
  await Vue.nextTick();
  vm.dialogShow = true;
  await Vue.nextTick();
  assert.equal(calls, 2);
  assert.equal(vm.previewError, '');
  responses[1].resolve(sample('retry succeeded'));
  await flush();
  assert.equal(vm.renderData[0].messages[0].message, 'retry succeeded');
  vm.$destroy();
});

test('request rejection without a message has a translated fallback', async () => {
  const vm = preview(async () => { throw ''; });
  await vm.loadPreview();
  assert.equal(vm.previewError, '模板预览失败，请稍后重试');
  assert.equal(vm.oldTemplate, '');
  vm.$destroy();
});

test('older success cannot clear loading or replace a newer template result', async () => {
  const responses = [deferred(), deferred()];
  let calls = 0;
  const vm = preview(() => responses[calls++].promise);
  vm.dialogShow = true;
  await Vue.nextTick();
  vm.template = 'B';
  await Vue.nextTick();
  responses[0].resolve(sample('stale A'));
  await flush();
  assert.equal(vm.loading, true);
  assert.equal(vm.renderData.length, 0);
  responses[1].resolve(sample('latest B'));
  await flush();
  assert.equal(vm.oldTemplate, 'B');
  assert.equal(vm.renderData[0].messages[0].message, 'latest B');
  vm.$destroy();
});

test('older failure cannot erase a newer successful result', async () => {
  const responses = [deferred(), deferred()];
  let calls = 0;
  const vm = preview(() => responses[calls++].promise);
  vm.dialogShow = true;
  await Vue.nextTick();
  vm.template = 'B';
  await Vue.nextTick();
  responses[1].resolve(sample('latest B'));
  await flush();
  responses[0].reject(new Error('stale failure'));
  await flush();
  assert.equal(vm.previewError, '');
  assert.equal(vm.oldTemplate, 'B');
  assert.equal(vm.renderData[0].messages[0].message, 'latest B');
  vm.$destroy();
});

for (const close of ['handleConfirm', '$destroy']) {
  test(`${close} invalidates an in-flight preview`, async () => {
    const response = deferred();
    const vm = preview(() => response.promise);
    vm.dialogShow = true;
    await Vue.nextTick();
    vm[close]();
    response.resolve(sample('too late'));
    await flush();
    assert.equal(vm.renderData.length, 0);
    assert.equal(vm.oldTemplate, '');
    assert.equal(vm.loading, false);
    if (close !== '$destroy') vm.$destroy();
  });
}

test('empty template invalidates a pending request without caching it', async () => {
  const response = deferred();
  const vm = preview(() => response.promise);
  vm.dialogShow = true;
  await Vue.nextTick();
  vm.template = '';
  await Vue.nextTick();
  response.resolve(sample('stale'));
  await flush();
  assert.equal(vm.loading, false);
  assert.equal(vm.oldTemplate, '');
  assert.equal(vm.renderData.length, 0);
  vm.$destroy();
});

test('scenario changes retain the existing action and do not reuse another scenario cache', async () => {
  const calls = [];
  const vm = preview(async params => { calls.push(params); return sample(params.scenario); }, { scenario: 'os' });
  vm.dialogShow = true;
  await flush();
  vm.scenario = 'service';
  await flush();
  assert.deepEqual(calls, [{ scenario: 'os', template: 'A' }, { scenario: 'service', template: 'A' }]);
  assert.equal(vm.renderData[0].messages[0].message, 'service');
  vm.$destroy();
});

test('notice preview forwards the current draft item and strategy identity without generating defaults', async () => {
  const calls = [];
  const item = {
    expression: 'a+b', functions: [],
    query_configs: ['a', 'b'].map(alias => ({
      alias, data_source_label: 'prometheus', data_type_label: 'time_series', expression_mode: 'promql',
      promql: 'vector(1)', agg_interval: 60,
    })),
  };
  const vm = preview(async params => { calls.push(params); return sample('draft'); }, {
    previewItem: item, strategyId: '11910', bkBizId: 2,
  });
  vm.dialogShow = true;
  await flush();
  assert.deepEqual(JSON.parse(JSON.stringify(calls)), [{
    template: 'A', preview_item: item, strategy_id: 11910, bk_biz_id: 2,
  }]);
  assert.equal('query_output_config' in calls[0].preview_item, false);
  vm.$destroy();
});

test('preview forwards explicit null and custom output configuration unchanged', async () => {
  const calls = [];
  const vm = preview(async params => { calls.push(JSON.parse(JSON.stringify(params))); return sample('draft'); }, {
    previewItem: Vue.observable({ expression: 'a+b', query_output_config: null }), bkBizId: 2,
  });
  vm.dialogShow = true;
  await flush();
  assert.equal(calls[0].strategy_id, 0);
  assert.equal(calls[0].preview_item.query_output_config, null);
  vm.previewItem.query_output_config = namedOutputConfig;
  await flush();
  assert.deepEqual(calls[1].preview_item.query_output_config, namedOutputConfig);
  vm.$destroy();
});

test('query and expression changes invalidate the same-template cache, including while the dialog is closed', async () => {
  const calls = [];
  const vm = preview(async params => { calls.push(JSON.parse(JSON.stringify(params))); return sample('draft'); }, {
    previewItem: Vue.observable({ expression: 'a+b', query_output_config: namedOutputConfig }), bkBizId: 2,
  });
  vm.dialogShow = true;
  await flush();
  vm.previewItem.expression = 'a-b';
  await flush();
  assert.equal(calls.length, 2);
  assert.equal(calls[1].preview_item.expression, 'a-b');
  vm.dialogShow = false;
  await Vue.nextTick();
  vm.previewItem = { expression: 'a', query_output_config: null };
  await flush();
  assert.equal(calls.length, 2);
  vm.dialogShow = true;
  await flush();
  assert.equal(calls.length, 3);
  assert.equal(calls[2].preview_item.query_output_config, null);
  vm.$destroy();
});

test('an older draft response cannot replace the current configuration preview', async () => {
  const responses = [deferred(), deferred()];
  let calls = 0;
  const vm = preview(() => responses[calls++].promise, {
    previewItem: { expression: 'a+b', query_output_config: namedOutputConfig }, bkBizId: 2,
  });
  vm.dialogShow = true;
  await Vue.nextTick();
  vm.previewItem = { expression: 'a-b', query_output_config: null };
  await Vue.nextTick();
  responses[1].resolve(sample('new config'));
  await flush();
  responses[0].resolve(sample('old config'));
  await flush();
  assert.equal(vm.renderData[0].messages[0].message, 'new config');
  assert.equal(JSON.parse(vm.oldPreviewContext).preview_item.query_output_config, null);
  vm.$destroy();
});

test('strategy and business changes invalidate the preview context', async () => {
  const calls = [];
  const vm = preview(async params => { calls.push(params); return sample('draft'); }, {
    previewItem: { query_output_config: namedOutputConfig }, strategyId: 11910, bkBizId: 2,
  });
  vm.dialogShow = true;
  await flush();
  vm.strategyId = 11993;
  await flush();
  vm.bkBizId = 3;
  await flush();
  assert.equal(calls.length, 3);
  assert.equal(calls[1].strategy_id, 11993);
  assert.equal(calls[2].bk_biz_id, 3);
  vm.$destroy();
});

test('legacy scenario preview ignores the new draft context and preserves its API parameters', async () => {
  const calls = [];
  const vm = preview(async params => { calls.push(params); return sample('legacy'); }, {
    scenario: 'os', previewItem: { query_output_config: namedOutputConfig }, strategyId: 11910, bkBizId: 2,
  });
  vm.dialogShow = true;
  await flush();
  assert.deepEqual(calls, [{ scenario: 'os', template: 'A' }]);
  vm.$destroy();
});

test('fixed-example notice is visible and request errors remain text nodes', () => {
  const vm = preview();
  const payload = '<img src=x onerror=alert(1)>';
  vm.previewError = payload;
  const nodes = allNodes(vm._render());
  const notice = nodes.find(node => node.data?.staticClass === 'preview-example-tip');
  const error = nodes.find(node => node.data?.staticClass === 'preview-error');
  assert.equal(text(notice).trim(), '预览使用固定示例数据，不是当前策略的查询值。');
  assert.equal(text(error).trim(), payload);
  assert.equal(error.data.attrs.role, 'alert');
  assert.equal(error.data.domProps?.innerHTML, undefined);
  vm.$destroy();
});

test('per-message errors are shown as text while the existing mail HTML branch remains', () => {
  const component = loadComponent(contentFile);
  const error = '<script>alert(1)</script>';
  const vm = new Vue({
    ...component,
    propsData: { renderList: [{ name: 'mail', type: 'mail', message: '<b>safe content</b>', error }] },
    methods: { $t: value => value },
  });
  const nodes = allNodes(vm._render());
  const errorNode = nodes.find(node => node.data?.staticClass === 'item-error');
  assert.equal(text(errorNode).trim(), `模板渲染失败: ${error}`);
  assert.equal(errorNode.data.domProps?.innerHTML, undefined);
  assert.equal(errorNode.data.attrs.role, 'alert');
  assert.ok(nodes.some(node => node.data?.domProps?.innerHTML === '<b>safe content</b>'));
  vm.$destroy();
});

test('message processing preserves errors and the existing mail sanitizer', () => {
  const vm = preview();
  vm.renderData = [{ type: 'mail', messages: [{ message: 'body', error: 'render failure' }] }];
  assert.equal(vm.renderTemplate[0].message, 'sanitized:body');
  assert.equal(vm.renderTemplate[0].error, 'render failure');
  vm.renderData = [{ type: 'weixin', messages: [{ message: '<style>a{color:red}</style>body', error: '' }] }];
  assert.equal(vm.renderTemplate[0].message, 'body');
  vm.$destroy();
});

test('variable table displays structured examples as JSON without changing the metadata object', () => {
  const component = loadComponent(variablesFile);
  const example = { A: { value: 4, state: 'SUCCESS' }, RESULT: { value: 10, state: 'SUCCESS' } };
  const source = [{ name: 'alarm', items: [
    { id: 'alarm.ref_values', description: example },
    { id: 'text', description: 'text' },
    { id: 'empty', description: null },
    { id: 'array', description: [1, 2] },
  ] }];
  const vm = new Vue({ ...component, propsData: { variateList: source } });
  assert.equal(vm.tableData[0].description, JSON.stringify(example));
  assert.equal(vm.tableData[1].description, 'text');
  assert.equal(vm.tableData[2].description, null);
  assert.equal(vm.tableData[3].description, '[1,2]');
  assert.equal(source[0].items[0].description, example);
  vm.$destroy();
});
