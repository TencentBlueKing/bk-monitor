const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const ts = require('typescript');
const Vue = require('vue');
const compiler = require('vue/compiler-sfc');

const root = path.resolve(__dirname, '../src/monitor-pc/pages/collector-config');
const translate = value => value;
const flush = () => new Promise(resolve => setImmediate(resolve));
const h = (type, props, ...children) => ({ type, props: props || {}, children: children.flat(Infinity) });
const named = name => ({ name });
const dependencies = {
  DetailLoadError: named('DetailLoadError'),
  DetailSkeleton: named('DetailSkeleton'),
  EmptyStatus: named('EmptyStatus'),
  HistoryDialog: named('HistoryDialog'),
};

function transpile(source, fileName) {
  const result = ts.transpileModule(source, {
    fileName,
    reportDiagnostics: true,
    compilerOptions: {
      module: ts.ModuleKind.CommonJS,
      target: ts.ScriptTarget.ES2022,
      jsx: ts.JsxEmit.React,
      jsxFactory: 'h',
    },
  });
  assert.equal(result.diagnostics.length, 0, fileName);
  return result.outputText;
}

function loadModule(source, fileName, requireDependency = () => {}) {
  const module = { exports: {} };
  new Function('require', 'module', 'exports', transpile(source, fileName))(requireDependency, module, module.exports);
  return module.exports;
}

const DetailRequest = loadModule(
  fs.readFileSync(path.join(root, 'collector-detail/detail-request.ts'), 'utf8'),
  'detail-request.ts'
).default;
const { TabEnum } = loadModule(
  fs.readFileSync(path.join(root, 'collector-detail/typings/detail.ts'), 'utf8'),
  'detail.ts'
);

// Run the actual class members without importing unrelated browser-only page components.
function pageClass(fileName, globals = {}) {
  const source = ts.createSourceFile(
    fileName,
    fs.readFileSync(path.join(root, fileName), 'utf8'),
    ts.ScriptTarget.Latest,
    true,
    ts.ScriptKind.TSX
  );
  const original = source.statements.find(ts.isClassDeclaration);
  const component = ts.factory.updateClassDeclaration(
    original,
    undefined,
    ts.factory.createIdentifier('Subject'),
    undefined,
    undefined,
    original.members
  );
  const transformed = ts.transform(component, [
    context => node => {
      const visit = child => (ts.isDecorator(child) ? undefined : ts.visitEachChild(child, visit, context));
      return ts.visitNode(node, visit);
    },
  ]);
  const printer = ts.createPrinter();
  const code = source.statements
    .filter(ts.isEnumDeclaration)
    .map(node => printer.printNode(ts.EmitHint.Unspecified, node, source))
    .concat(printer.printNode(ts.EmitHint.Unspecified, transformed.transformed[0], source))
    .join('\n');
  transformed.dispose();
  const values = {
    h,
    window: { i18n: { t: translate }, clearTimeout() {} },
    random: () => 'key',
    DetailRequest,
    TabEnum,
    formatWithTimezone: value => value,
    ...dependencies,
    ...globals,
  };
  return new Function(...Object.keys(values), `${transpile(code, fileName)}; return Subject;`)(
    ...Object.values(values)
  );
}

function api() {
  const calls = { detail: [], targets: [] };
  const request = type => (params, options) => {
    let resolve;
    let reject;
    const promise = new Promise((yes, no) => {
      resolve = yes;
      reject = no;
    });
    calls[type].push({ params, options, resolve, reject });
    return promise;
  };
  return {
    calls,
    frontendCollectConfigDetail: request('detail'),
    frontendCollectConfigTargetInfo: request('targets'),
  };
}

const detailData = name => ({ basic_info: { name }, extend_info: {}, metric_list: [], runtime_params: [] });
const targetData = rows => ({ target_node_type: 'TOPO', table_data: rows });
const row = { bk_inst_name: 'example-node', count: 2, labels: [] };

function detailPage() {
  const service = api();
  const Subject = pageClass('collector-detail/collector-detail.tsx', service);
  const subject = new Subject();
  subject.collectId = 101;
  subject.$route = { name: 'collect-config-detail', params: { id: '101' }, query: {} };
  subject.getCollectConfigListItem = () => {};
  subject.handleTabChange = () => {
    subject.getDetails();
    subject.getTargetInfoData();
  };
  return { subject, ...service };
}

function configuration(subject) {
  const Subject = pageClass('collector-detail/collector-configuration.tsx');
  const view = Object.assign(new Subject(), {
    id: subject.collectId,
    detailData: subject.detailData,
    detailLoaded: subject.requests.detail.loaded,
    loading: subject.requests.detail.loading,
    loadError: subject.requests.detail.error,
    targetInfo: subject.targetInfo,
    targetLoaded: subject.requests.targets.loaded,
    tableLoading: subject.requests.targets.loading,
    targetError: subject.requests.targets.error,
    authority: { MANAGE_AUTH: true },
    $t: translate,
    $emit: event => (event === 'retryTargets' ? subject.getTargetInfoData() : subject.getDetails()),
  });
  view.getDetailData();
  return view.render();
}

const nodes = node => (!node ? [] : [node, ...(node.children || node.componentOptions?.children || []).flatMap(nodes)]);
const isType = (node, type) =>
  node.type === type || node.tag === type || node.componentOptions?.Ctor.options.name === type;
const find = (tree, type) => nodes(tree).find(node => isType(node, type));
const textOf = tree =>
  nodes(tree)
    .map(node => (typeof node === 'string' ? node : node.text || ''))
    .join(' ');

const sideFile = 'collector-config-detail/collector-config-detail.vue';
const sideDescriptor = compiler.parse({
  source: fs.readFileSync(path.join(root, sideFile), 'utf8'),
  filename: sideFile,
});
assert.equal(sideDescriptor.errors.length, 0);
const sideTemplate = compiler.compileTemplate({ source: sideDescriptor.template.content, filename: sideFile });
assert.equal(sideTemplate.errors.length, 0);
const sideRender = new Function(`${sideTemplate.code}; return { render, staticRenderFns };`)();

function sidePanel() {
  const service = api();
  const options = loadModule(sideDescriptor.script.content, 'side.js', id => {
    if (id === 'monitor-api/modules/collecting') return service;
    if (id.includes('detail-request')) return { default: DetailRequest };
    if (id.includes('timezone')) return { formatWithTimezone: value => value };
    const name = Object.keys(dependencies).find(key =>
      id.includes(key.replace(/[A-Z]/g, value => `-${value.toLowerCase()}`).slice(1))
    );
    return { default: name ? dependencies[name] : named('Stub') };
  }).default;
  const events = [];
  const subject = new Vue({
    ...options,
    ...sideRender,
    inject: [],
    propsData: { sideData: { id: 101 }, sideShow: true },
    beforeCreate() {
      this.$t = translate;
      this.$store = { getters: { bizId: 0, bizList: [] } };
      this.authority = { MANAGE_AUTH: true };
    },
  });
  subject.$on('set-hide', value => events.push(value));
  return { subject, events, ...service };
}

test('detail: target failure leaves basic data visible and retry calls only targets', async () => {
  const { subject, calls } = detailPage();
  const basic = subject.getDetails();
  const targets = subject.getTargetInfoData();
  assert.equal(nodes(configuration(subject)).filter(node => isType(node, dependencies.DetailSkeleton)).length, 2);
  assert.equal(calls.detail[0].params.with_target_info, false);
  assert.equal(calls.detail[0].options.needMessage, false);
  assert.equal(calls.targets[0].options.needMessage, false);
  calls.detail[0].resolve(detailData('example-config'));
  calls.targets[0].reject(new Error('unavailable'));
  await Promise.all([basic, targets]);
  let tree = configuration(subject);
  assert.match(textOf(tree), /example-config/);
  assert.ok(find(tree, dependencies.DetailLoadError));
  assert.equal(find(tree, 'bk-table'), undefined);
  assert.equal(find(tree, dependencies.EmptyStatus), undefined);
  const retry = find(tree, dependencies.DetailLoadError).props.onRetry();
  assert.equal(calls.detail.length, 1);
  calls.targets[1].resolve(targetData([]));
  await retry;
  tree = configuration(subject);
  assert.ok(find(tree, dependencies.EmptyStatus));
  assert.equal(find(tree, dependencies.DetailLoadError), undefined);
});

test('detail: basic failure keeps successful targets with a neutral count label', async () => {
  const { subject, calls } = detailPage();
  const basic = subject.getDetails();
  const targets = subject.getTargetInfoData();
  calls.detail[0].reject(new Error('unavailable'));
  calls.targets[0].resolve(targetData([row]));
  await Promise.all([basic, targets]);
  const tree = configuration(subject);
  assert.ok(find(tree, dependencies.DetailLoadError));
  assert.ok(find(tree, 'bk-table'));
  assert.ok(nodes(tree).some(node => node.props?.label === '数量'));
  assert.equal(
    nodes(tree).some(node => node.props?.label === 'IP'),
    false
  );
});

test('detail: changing configuration invalidates old data, errors and loading completion', async () => {
  const { subject, calls } = detailPage();
  const first = subject.getDetails();
  const firstTargets = subject.getTargetInfoData();
  subject.$route.params.id = '102';
  subject.handleCollectIdChange('102');
  assert.equal(calls.detail[0].options.signal.aborted, true);
  calls.detail[0].resolve(detailData('old-config'));
  calls.targets[0].reject(new Error('old-failure'));
  await Promise.all([first, firstTargets]);
  assert.equal(subject.requests.detail.loading, true);
  assert.equal(subject.requests.targets.error, false);
  assert.equal(subject.detailData.basic_info.name, undefined);
  calls.detail[1].resolve(detailData('new-config'));
  calls.targets[1].resolve(targetData([row]));
  await flush();
  assert.equal(subject.detailData.basic_info.name, 'new-config');
  subject.beforeDestroy();
});

test('side: target failure keeps the panel open; retry and empty state are local', async () => {
  const { subject, calls, events } = sidePanel();
  assert.equal(nodes(subject._render()).filter(node => isType(node, 'DetailSkeleton')).length, 2);
  assert.equal(calls.detail[0].params.with_target_info, false);
  assert.equal(calls.detail[0].options.needMessage, false);
  assert.equal(calls.targets[0].options.needMessage, false);
  calls.detail[0].resolve(detailData('example-config'));
  calls.targets[0].reject(new Error('unavailable'));
  await flush();
  let tree = subject._render();
  assert.match(textOf(tree), /example-config/);
  const error = find(tree, 'DetailLoadError');
  assert.ok(error);
  assert.equal(find(tree, 'bk-table'), undefined);
  assert.equal(find(tree, 'EmptyStatus'), undefined);
  assert.equal(events.length, 0);
  const retry = error.componentOptions.listeners.retry();
  assert.equal(calls.detail.length, 1);
  calls.targets[1].resolve(targetData([]));
  await retry;
  tree = subject._render();
  assert.ok(find(tree, 'EmptyStatus'));
  assert.equal(find(tree, 'DetailLoadError'), undefined);
  subject.$destroy();
});

test('side: basic failure allows targets and basic retry without reloading targets', async () => {
  const { subject, calls, events } = sidePanel();
  calls.detail[0].reject(new Error('unavailable'));
  calls.targets[0].resolve(targetData([row]));
  await flush();
  let tree = subject._render();
  assert.ok(find(tree, 'bk-table'));
  assert.ok(nodes(tree).some(node => node.data?.attrs?.label === '数量'));
  const retry = find(tree, 'DetailLoadError').componentOptions.listeners.retry();
  assert.equal(calls.targets.length, 1);
  calls.detail[1].resolve(detailData('recovered-config'));
  await retry;
  tree = subject._render();
  assert.match(textOf(tree), /recovered-config/);
  assert.equal(find(tree, 'DetailLoadError'), undefined);
  assert.equal(events.length, 0);
  subject.$destroy();
});

test('side: reopening the same configuration retains basic data through a failed refresh', async () => {
  const { subject, calls } = sidePanel();
  calls.detail[0].resolve(detailData('retained-config'));
  calls.targets[0].resolve(targetData([row]));
  await flush();
  subject.sideShow = false;
  await Vue.nextTick();
  subject.sideShow = true;
  await Vue.nextTick();
  assert.match(textOf(subject._render()), /retained-config/);
  calls.detail[1].reject(new Error('refresh-failure'));
  calls.targets[1].resolve(targetData([row]));
  await flush();
  const tree = subject._render();
  assert.match(textOf(tree), /retained-config/);
  assert.equal(find(tree, 'DetailLoadError').data.attrs.compact, true);
  subject.$destroy();
});

test('side: configuration switches and closing ignore delayed responses', async () => {
  const { subject, calls } = sidePanel();
  subject.sideData = { id: 102 };
  await Vue.nextTick();
  calls.detail[0].resolve(detailData('old-config'));
  calls.targets[0].reject(new Error('old-failure'));
  await flush();
  assert.equal(subject.basicInfo, null);
  assert.equal(subject.requests.detail.loading, true);
  assert.equal(subject.requests.targets.error, false);
  assert.equal(calls.detail[1].params.id, 102);
  subject.sideShow = false;
  await Vue.nextTick();
  calls.detail[1].resolve(detailData('closed-config'));
  calls.targets[1].resolve(targetData([row]));
  await flush();
  assert.equal(subject.basicInfo, null);
  assert.equal(subject.requests.targets.loaded, false);
  subject.$destroy();
});
