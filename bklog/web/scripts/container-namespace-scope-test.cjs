/* global require, __dirname, process */
// Execute the real component code with Vue reactivity and mocked HTTP / UI boundaries.
// Run: node scripts/container-namespace-scope-test.cjs
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { execFileSync } = require('node:child_process');
const ts = require('typescript');
const Vue = require('vue');
const compiler = require('vue/compiler-sfc');

const root = path.resolve(__dirname, '..');
const current = 'src/views/manage-v2/log-collection/components/business-comp/step2/container-collection/';
const legacy = 'src/components/collection-access/components/step-add/';
const requests = [];
const timers = new Map();
const mounted = [];
const scopes = [];
let timerId = 0;
const http = {
  request: async (name, args) => {
    requests.push({ name, ...args });
    return { code: 0, data: name === 'container/getWorkLoadType' ? ['Deployment'] : [] };
  },
};
const store = { getters: { bkBizId: 2 } };
const jsx = (tag, props, ...children) => ({ tag, props: props || {}, children: children.flat(Infinity) });

function evaluate(source, filename, globals = {}) {
  const js = ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.CommonJS,
      jsx: ts.JsxEmit.React,
      jsxFactory: 'jsx',
      target: ts.ScriptTarget.ES2020,
    },
  }).outputText;
  const module = { exports: {} };
  vm.runInNewContext(
    js,
    {
      module,
      exports: module.exports,
      jsx,
      console,
      ...globals,
      setTimeout: callback => {
        timerId += 1;
        timers.set(timerId, callback);
        return timerId;
      },
      clearTimeout: id => timers.delete(id),
      require: name => {
        if (name === 'vue')
          return {
            ...Vue,
            defineComponent: options => options,
            onMounted: callback => mounted.push(callback),
            onUnmounted: () => {},
            onBeforeUnmount: () => {},
          };
        if (name === 'vuex')
          return {
            mapGetters: mapping =>
              Object.fromEntries(Object.entries(mapping).map(([key, getter]) => [key, () => store.getters[getter]])),
          };
        if (name === '@/api') return { default: http };
        if (name === '@/hooks/use-store') return { default: () => store };
        if (name === '@/hooks/use-locale') return { default: () => ({ t: text => text }) };
        if (name === '@/common/util') return { random: () => 'label-id' };
        if (
          name === 'tippy.js' ||
          name.endsWith('.scss') ||
          name.startsWith('./') ||
          name.startsWith('../') ||
          name === '@/components/empty-status' ||
          name === '@/components/empty-status/index.vue'
        )
          return { default: name };
        throw new Error(`Unsupported boundary: ${name}`);
      },
    },
    { filename },
  );
  return module.exports.default;
}

function load(file) {
  const filename = path.join(root, file);
  const source = process.argv.includes('--baseline')
    ? execFileSync('git', ['show', `upstream/master:bklog/web/${file}`], { encoding: 'utf8' })
    : fs.readFileSync(filename, 'utf8');
  return evaluate(file.endsWith('.vue') ? compiler.parseComponent(source).script.content : source, filename);
}
function setup(file, props, emit = () => {}) {
  const scope = Vue.effectScope();
  scopes.push(scope);
  return scope.run(() => load(file).setup(props, { emit }));
}
function find(node, predicate) {
  if (!node || typeof node !== 'object') return undefined;
  if (predicate(node)) return node;
  return (node.children || []).map(child => find(child, predicate)).find(Boolean);
}
const plain = value => JSON.parse(JSON.stringify(value));
async function flush() {
  await Vue.nextTick();
  const pending = [...timers.values()];
  timers.clear();
  pending.forEach(callback => callback());
  await Promise.resolve();
  await Vue.nextTick();
  await Promise.resolve();
}
function latest(name) {
  return requests.filter(item => item.name === name).at(-1);
}

async function main() {
  const config = Vue.reactive({
    namespaces: ['system'],
    containerNameList: ['sidecar'],
    container: { workload_type: 'Deployment', workload_name: '', container_name: '' },
    label_selector: { match_expressions: [] },
    noQuestParams: {
      namespaceStr: 'system',
      namespacesExclude: '!=',
      containerExclude: '!=',
      scopeSelectShow: { namespace: false, containerName: false, label: true, annotation: true, load: true },
    },
  });
  setup(
    `${current}workload-selection.tsx`,
    Vue.reactive({ conItem: config, container: config.container, bcsClusterId: 'cluster' }),
  );
  mounted.splice(0).forEach(callback => callback());
  await flush();
  assert.deepEqual(plain(latest('container/getWorkLoadName').query), {
    type: 'Deployment',
    bk_biz_id: 2,
    namespaces_exclude: 'system',
    bcs_cluster_id: 'cluster',
  });
  const beforeSwitch = requests.length;
  config.noQuestParams.namespacesExclude = '=';
  await flush();
  assert.ok(requests.length > beforeSwitch, 'operator switch must refetch even when names stay the same');
  assert.equal(latest('container/getWorkLoadName').query.namespace, 'system');
  assert.ok(!('namespaces_exclude' in latest('container/getWorkLoadName').query));
  config.noQuestParams.namespaceStr = '';
  await flush();
  assert.equal(latest('container/getWorkLoadName').query.namespace, '', 'clearing scope must refetch all candidates');
  config.noQuestParams.namespaceStr = 'system';
  config.noQuestParams.namespacesExclude = '!=';
  await flush();

  const editRender = setup(`${current}config-log-set-edit-item.tsx`, {
    config,
    bcsClusterId: 'cluster',
    isNode: false,
    editType: 'label_selector',
    clusterList: [],
  });
  const { labelParams } = find(editRender(), node => node.tag === './label-choose-dialog').props;
  assert.equal(labelParams.namespacesExclude, '!=');
  const labelProps = Vue.reactive({ labelParams, clusterList: [], isShowDialog: false });
  setup(`${current}label-choose-dialog.tsx`, labelProps);
  labelProps.isShowDialog = true;
  await flush();
  assert.deepEqual(plain(latest('container/getPodTree').query), {
    bcs_cluster_id: 'cluster',
    type: 'pod',
    bk_biz_id: 2,
    namespaces_exclude: 'system',
  });
  labelProps.isShowDialog = false;
  await flush();
  labelProps.labelParams = { ...labelParams, namespacesExclude: '=', namespaceStr: 'app' };
  labelProps.isShowDialog = true;
  await flush();
  assert.equal(latest('container/getPodTree').query.namespace, 'app');
  assert.ok(!('namespaces_exclude' in latest('container/getPodTree').query));

  const previewRender = setup(`${current}config-cluster-box.tsx`, {
    config,
    bcsClusterId: 'cluster',
    isNode: false,
    clusterList: [],
    nameSpacesSelectList: [],
  });
  const tree = previewRender();
  let preview = find(tree, node => node.tag === './config-view-dialog').props.viewQueryParams;
  assert.deepEqual(plain(preview.namespaces_exclude), ['system']);
  assert.ok(!('namespaces' in preview));
  assert.equal(preview.container.container_name_exclude, 'sidecar');
  assert.ok(!('container_name' in preview.container));
  assert.deepEqual(plain(find(tree, node => node.tag === 'bk-tag-input').props.value), ['sidecar']);
  const previewProps = Vue.reactive({ isShowDialog: false, viewQueryParams: preview });
  setup(`${current}config-view-dialog.tsx`, previewProps);
  previewProps.isShowDialog = true;
  await flush();
  assert.deepEqual(plain(latest('container/getLabelHitView').data.namespaces_exclude), ['system']);
  assert.equal(latest('container/getLabelHitView').data.container.container_name_exclude, 'sidecar');
  config.noQuestParams.namespacesExclude = '=';
  config.noQuestParams.containerExclude = '=';
  preview = find(previewRender(), node => node.tag === './config-view-dialog').props.viewQueryParams;
  assert.deepEqual(plain(preview.namespaces), ['system']);
  assert.ok(!('namespaces_exclude' in preview));
  assert.equal(preview.container.container_name, 'sidecar');
  assert.ok(!('container_name_exclude' in preview.container));

  const oldWorkload = load(`${legacy}container-target-item.vue`);
  const oldContext = {
    conItem: config,
    typeListIDStrList: ['Deployment'],
    nameRequestId: 0,
    formData: config.container,
    bkBizId: 2,
    bcsClusterId: 'cluster',
    $http: http,
  };
  config.noQuestParams.namespacesExclude = '!=';
  oldWorkload.methods.getWorkLoadNameList.call(oldContext);
  assert.equal(latest('container/getWorkLoadName').query.namespaces_exclude, 'system');
  assert.ok(!('namespace' in latest('container/getWorkLoadName').query));
  config.noQuestParams.namespacesExclude = '=';
  const switchRequests = requests.length;
  oldContext.getWorkLoadNameList = () => oldWorkload.methods.getWorkLoadNameList.call(oldContext);
  oldWorkload.watch.namespaceScope.handler.call(oldContext);
  await flush();
  assert.ok(requests.length > switchRequests);
  assert.equal(latest('container/getWorkLoadName').query.namespace, 'system');

  const oldLabels = load(`${legacy}label-target-dialog.vue`);
  const oldLabelContext = {
    labelParams: { ...labelParams },
    treeRequestId: 0,
    $http: http,
    initTreeList: () => [],
    getResultStrList: () => [],
  };
  oldLabels.methods.getTreeList.call(oldLabelContext);
  assert.equal(latest('container/getPodTree').query.namespaces_exclude, 'system');
  assert.ok(!('namespace' in latest('container/getPodTree').query));
  oldLabelContext.labelParams.namespacesExclude = '=';
  oldLabels.methods.getTreeList.call(oldLabelContext);
  assert.equal(latest('container/getPodTree').query.namespace, 'system');
  oldLabelContext.labelParams.type = 'node';
  oldLabels.methods.getTreeList.call(oldLabelContext);
  assert.ok(!('namespace' in latest('container/getPodTree').query));
  assert.ok(!('namespaces_exclude' in latest('container/getPodTree').query));

  const oldConfigs = load(`${legacy}configs-select.vue`);
  config.noQuestParams.namespacesExclude = '!=';
  const oldConfigContext = { formData: { configs: [config], bcs_cluster_id: 'cluster' }, bkBizId: 2, isNode: false };
  oldConfigs.methods.handelShowDialog.call(oldConfigContext, 0, 'label');
  assert.equal(oldConfigContext.currentSelector.namespacesExclude, '!=');

  // Run the unchanged save function from the source; unrelated path/encoding helpers are boundaries.
  const saveFile = path.join(
    root,
    'src/views/manage-v2/log-collection/components/create-operation/step2-configuration.tsx',
  );
  const saveSource = ts.createSourceFile(
    saveFile,
    fs.readFileSync(saveFile, 'utf8'),
    ts.ScriptTarget.Latest,
    true,
    ts.ScriptKind.TSX,
  );
  let saveExpression;
  function visit(node) {
    if (ts.isVariableDeclaration(node) && node.name.getText(saveSource) === 'handleContainerRequestData') {
      saveExpression = node.initializer.getText(saveSource);
    }
    ts.forEachChild(node, visit);
  }
  visit(saveSource);
  assert.ok(saveExpression, 'save function must exist');
  const save = evaluate(`export default ${saveExpression}`, saveFile, {
    collectorType: Vue.ref('container_log_config'),
    logType: Vue.ref('row'),
    clearSectionLogFields: params => params,
    formatExcludeFiles: files => files,
    extractPaths: params => params.paths,
    isEmptyExtraLabels: labels => !labels.length,
  });
  config.params = { paths: ['/logs/app.log'], exclude_files: [] };
  let saved = save({}, [config], false, false, [], 'cluster').configs[0];
  assert.deepEqual(plain(saved.namespaces_exclude), ['system']);
  assert.ok(!('namespaces' in saved));
  config.noQuestParams.namespacesExclude = '=';
  [saved] = save({}, [config], false, false, [], 'cluster').configs;
  assert.deepEqual(plain(saved.namespaces), ['system']);
  assert.ok(!('namespaces_exclude' in saved));

  await testSelectors(save);
  await testLegacyLabelLifecycle();
  await testWorkloadResponses();
  scopes.forEach(scope => scope.stop());
  console.log(
    'container-namespace-scope-test: passed (real component code, mocked HTTP / UI; no browser or live backend)',
  );
}
main().catch(error => {
  console.error(error);
  process.exitCode = 1;
});

async function testSelectors(save) {
  const keyEditor = setup(`${current}label-item-choose.tsx`, {
    matchItem: { key: 'tier', operator: 'In', value: 'web' },
  });
  const keyInput = () => find(keyEditor(), node => node.tag === 'bk-input');
  const validateKey = () => find(keyEditor(), node => node.tag === 'bk-form').props.props.rules.key[0].validator();
  assert.equal(validateKey(), true);
  keyInput().props['on-input']('bad key');
  assert.equal(validateKey(), false, 'label and annotation keys must validate the actual key field');
  keyInput().props['on-input']('team/log-tier');
  assert.equal(validateKey(), true);

  // Drive the shared editor through its real parent, preview and unchanged save path.
  for (const selector of ['label_selector', 'annotation_selector']) {
    const expressionKey = selector === 'label_selector' ? 'match_expressions' : 'match_annotations';
    for (const operator of ['In', 'NotIn', 'Exists', 'DoesNotExist']) {
      const config = Vue.reactive({
        namespaces: ['app'],
        containerNameList: [],
        container: { workload_type: '', workload_name: '', container_name: '' },
        params: { paths: ['/logs/app.log'], exclude_files: [] },
        [selector]: { [expressionKey]: [{ key: 'tier', operator: 'In', value: 'web' }] },
        noQuestParams: { namespaceStr: 'app', namespacesExclude: '=', containerExclude: '=', scopeSelectShow: {} },
      });
      const parent = setup(
        `${current}config-log-set-edit-item.tsx`,
        {
          config,
          bcsClusterId: 'cluster',
          isNode: false,
          editType: selector,
          clusterList: [],
        },
        (event, payload) => {
          if (event === 'change') Object.assign(config, payload);
        },
      );
      const childProps = find(parent(), node => node.tag === './label-item-choose').props;
      const child = setup(`${current}label-item-choose.tsx`, { matchItem: childProps.matchItem }, (event, payload) => {
        if (event === 'change') childProps['on-change'](payload);
      });
      find(child(), node => node.tag === 'bk-select').props['on-selected'](operator);
      const expected = ['Exists', 'DoesNotExist'].includes(operator) ? '' : 'web';
      assert.equal(config[selector][expressionKey][0].value, expected, `${selector} ${operator}`);
      const preview = setup(`${current}config-cluster-box.tsx`, {
        config,
        bcsClusterId: 'cluster',
        isNode: false,
        clusterList: [],
        nameSpacesSelectList: [],
      });
      const params = find(preview(), node => node.tag === './config-view-dialog').props.viewQueryParams;
      assert.equal(params[selector][expressionKey][0].value, expected ? `(${expected})` : '');
      assert.equal(
        save({}, [config], false, false, [], 'cluster').configs[0][selector][expressionKey][0].value,
        expected,
      );
      // Switching back must not resurrect the hidden stale value.
      if (!expected) {
        find(child(), node => node.tag === 'bk-select').props['on-selected']('NotIn');
        assert.equal(config[selector][expressionKey][0].value, '');
      }
    }
  }

  const originalRequest = http.request;
  const pending = [];
  const fixture = [
    {
      id: 'cluster',
      name: 'cluster',
      type: 'cluster',
      children: [
        { id: 'empty', name: 'empty', type: 'namespace', children: [] },
        { id: 'app', name: 'app', type: 'namespace', children: [{ id: 'pod', name: 'pod', type: 'pod' }] },
      ],
    },
  ];
  http.request = (name, args) => {
    requests.push({ name, ...args });
    if (name === 'container/getPodTree') return Promise.resolve({ code: 0, data: fixture });
    return new Promise((resolve, reject) => pending.push({ resolve, reject, query: args.query }));
  };
  const props = Vue.reactive({
    labelParams: { bk_biz_id: 2, bcs_cluster_id: 'cluster', type: 'pod', namespaceStr: 'app', namespacesExclude: '=' },
    clusterList: [],
    isShowDialog: false,
  });
  const emitted = [];
  const render = setup(`${current}label-choose-dialog.tsx`, props, (event, payload) =>
    emitted.push({ event, payload: plain(payload) }),
  );
  props.isShowDialog = true;
  await flush();
  const tree = () => find(render(), node => node.tag === '../../../common-comp/tree-component');
  const click = (type, name, namespace = 'app') =>
    tree().props['on-click-node'](
      { id: name, name, type, children: [] },
      namespace ? { id: namespace, name: namespace, type: 'namespace' } : undefined,
    );
  const labels = () => plain(find(render(), node => node.props.class === 'main-right-bot'));
  const loading = () => find(render(), node => node.props.class === 'main-right-bot').props['v-bkloading'].isLoading;
  const response = value => ({ code: 0, data: [{ key: 'source', value }] });
  let before = pending.length;
  click('namespace', 'empty', 'cluster');
  click('cluster', 'cluster', '');
  assert.equal(pending.length, before, 'empty namespace/cluster must never query labels');

  click('pod', 'same-pod', 'app');
  click('pod', 'same-pod', 'other');
  assert.deepEqual(
    pending.slice(-2).map(item => item.query.namespace),
    ['app', 'other'],
  );
  pending.at(-2).resolve(response('A'));
  await flush();
  assert.equal(loading(), true, 'old completion must not stop current loading');
  assert.ok(!JSON.stringify(labels()).includes('A'), 'old response must not be selectable');
  pending.at(-1).resolve(response('B'));
  await flush();
  assert.equal(loading(), false);
  assert.ok(JSON.stringify(labels()).includes('B'));

  before = requests.length;
  props.labelParams = { ...props.labelParams, labelSelector: { match_expressions: [] } };
  await flush();
  assert.equal(requests.length, before, 'same scope must preserve candidates when other props change');
  const group = find(
    find(render(), node => node.props.class === 'main-right-bot'),
    node => node.tag === 'bk-checkbox-group',
  );
  group.props['on-change'](['label-id']);
  find(render(), node => node.tag === 'bk-dialog').props['on-confirm']();
  assert.equal(emitted.find(item => item.event === 'change').payload[0].value, 'B');

  click('pod', 'first');
  click('pod', 'second');
  pending.at(-1).resolve(response('new-label'));
  await flush();
  pending.at(-2).resolve(response('stale-label'));
  await flush();
  assert.ok(JSON.stringify(labels()).includes('new-label'));
  assert.ok(!JSON.stringify(labels()).includes('stale-label'));

  click('pod', 'closing');
  props.isShowDialog = false;
  await flush();
  pending.at(-1).resolve(response('closed-label'));
  await flush();
  assert.ok(!JSON.stringify(labels()).includes('closed-label'));
  props.isShowDialog = true;
  await flush();
  click('pod', 'invalidated');
  click('namespace', 'empty', 'cluster');
  pending.at(-1).resolve(response('empty-label'));
  await flush();
  assert.equal(loading(), false);
  assert.ok(!JSON.stringify(labels()).includes('empty-label'));

  click('pod', 'old-scope');
  const oldScopeRequest = pending.at(-1);
  props.labelParams.namespaceStr = 'other';
  await flush();
  assert.equal(latest('container/getPodTree').query.namespace, 'other');
  oldScopeRequest.resolve(response('old-scope-label'));
  await flush();
  assert.ok(!JSON.stringify(labels()).includes('old-scope-label'));

  props.labelParams.type = 'node';
  await flush();
  click('node', 'node-a', '');
  assert.ok(!('namespace' in pending.at(-1).query), 'node labels do not carry a namespace');
  pending.at(-1).resolve(response('node-label'));
  await flush();
  assert.ok(JSON.stringify(labels()).includes('node-label'));
  click('node', 'canceling', '');
  find(render(), node => node.tag === 'bk-dialog').props['on-cancel']();
  pending.at(-1).resolve(response('cancel-label'));
  await flush();
  assert.ok(!JSON.stringify(labels()).includes('cancel-label'), 'cancel must invalidate before parent updates props');

  // A tree request completing after close must not repopulate or auto-query labels.
  let resolveTree;
  http.request = (name, args) => {
    requests.push({ name, ...args });
    return new Promise(resolve => {
      resolveTree = resolve;
    });
  };
  props.isShowDialog = false;
  await flush();
  props.isShowDialog = true;
  await flush();
  props.isShowDialog = false;
  await flush();
  before = requests.length;
  resolveTree({
    code: 0,
    data: [
      {
        id: 'cluster',
        type: 'cluster',
        children: [
          { id: 'app', name: 'app', type: 'namespace', children: [{ id: 'late-pod', name: 'late-pod', type: 'pod' }] },
        ],
      },
    ],
  });
  await flush();
  assert.equal(requests.length, before, 'closed tree must not trigger auto label requests');
  http.request = originalRequest;
}

async function testLegacyLabelLifecycle() {
  const component = load(`${legacy}label-target-dialog.vue`);
  const pending = [];
  const emitted = [];
  const context = Object.assign(component.data(), {
    labelParams: { bk_biz_id: 2, bcs_cluster_id: 'cluster', type: 'pod', namespaceStr: 'app', labelSelector: [] },
    $http: { request: (name, args) => new Promise(resolve => pending.push({ name, query: args.query, resolve })) },
    $emit: (event, payload) => emitted.push({ event, payload: plain(payload) }),
  });
  for (const [name, method] of Object.entries(component.methods)) context[name] = method.bind(context);
  const click = (type, id, namespace = 'app') =>
    context.handleSelectTreeItem({
      data: { type, id },
      parent: { data: { type: 'namespace', id: namespace } },
    });
  const response = value => ({ code: 0, data: [{ key: 'source', value }] });
  click('pod', 'pod-a');
  click('pod', 'pod-b');
  pending[0].resolve(response('old'));
  await flush();
  assert.equal(context.labelLoading, true, 'legacy old completion must not stop current loading');
  assert.equal(context.matchSelectItemList.length, 0);
  pending[1].resolve(response('current'));
  await flush();
  context.matchSelectList = ['label-id'];
  click('pod', 'same-pod', 'other');
  assert.equal(context.matchCheckedItemList[0].value, 'current', 'selected labels survive a node change');
  assert.equal(pending.at(-1).query.namespace, 'other');
  assert.equal(context.matchSelectItemList.length, 0, 'old candidates must clear while loading');
  pending.at(-1).resolve(response('other'));
  await flush();
  context.matchSelectList = ['label-id'];
  context.handelConfirmLabel();
  assert.ok(
    emitted.some(
      item => item.event === 'config-label-change' && item.payload.labelSelector.some(label => label.value === 'other'),
    ),
  );
  click('pod', 'empty-invalidation');
  const old = pending.at(-1);
  const before = pending.length;
  click('namespace', 'empty');
  assert.equal(pending.length, before);
  old.resolve(response('stale-empty'));
  await flush();
  assert.equal(context.matchSelectItemList.length, 0);
  click('pod', 'closing');
  context.handelCancelDialog();
  pending.at(-1).resolve(response('stale-close'));
  await flush();
  assert.equal(context.matchSelectItemList.length, 0);
  context.labelParams.type = 'node';
  click('node', 'node-a');
  assert.ok(!('namespace' in pending.at(-1).query));
  context.resetSelect();
  context.getTreeList();
  const treeRequest = pending.at(-1);
  context.resetSelect();
  treeRequest.resolve({ code: 0, data: { type: 'cluster', id: 'old-cluster', children: [] } });
  await flush();
  assert.equal(context.treeList.length, 0, 'closed legacy tree must stay empty');
  assert.equal(context.treeLoading, false);

  // The old expression editor already clears unary values; lock in that behavior.
  const editor = load(`${legacy}match-label.vue`);
  for (const operator of ['In', 'NotIn', 'Exists', 'DoesNotExist']) {
    const item = Object.assign(editor.data(), {
      matchKey: 'tier',
      matchValue: 'web',
      matchOperator: operator,
      isLabel: false,
      expressInputIsDisabled: ['Exists', 'DoesNotExist'].includes(operator),
    });
    item.handleCancelMatch = editor.methods.handleCancelMatch.bind(item);
    editor.methods.handleAddMatch.call(item);
    assert.equal(item.matchList[0].value, item.expressInputIsDisabled ? '' : 'web');
  }
}

async function testWorkloadResponses() {
  const original = http.request;
  const pending = [];
  http.request = (name, args) => {
    if (name === 'container/getWorkLoadType') return Promise.resolve({ code: 0, data: ['Deployment'] });
    return new Promise(resolve => pending.push({ query: args.query, resolve }));
  };
  const config = Vue.reactive({
    noQuestParams: { namespaceStr: 'system', namespacesExclude: '!=' },
    container: { workload_type: 'Deployment', workload_name: '', container_name: '' },
  });
  const render = setup(`${current}workload-selection.tsx`, {
    conItem: config,
    container: config.container,
    bcsClusterId: 'cluster',
  });
  mounted.pop()();
  await flush();
  const previous = pending.splice(0);
  config.noQuestParams.namespacesExclude = '=';
  await flush();
  assert.equal(pending.at(-1).query.namespace, 'system');
  pending.at(-1).resolve({ code: 0, data: ['current-workload'] });
  await flush();
  previous.forEach(item => item.resolve({ code: 0, data: ['excluded-workload'] }));
  await flush();
  const names = () => find(render(), node => (node.props.class || '').includes('workload-name-select'));
  assert.ok(JSON.stringify(names()).includes('current-workload'));
  assert.ok(
    !JSON.stringify(names()).includes('excluded-workload'),
    'outdated reverse scope must never replace current candidates',
  );
  config.noQuestParams.namespaceStr = 'app';
  await flush();
  const clearing = pending.at(-1);
  find(render(), node => node.props.class === 'workload-type-select').props['on-selected']('');
  await flush();
  clearing.resolve({ code: 0, data: ['cleared-workload'] });
  await flush();
  assert.ok(!JSON.stringify(names()).includes('cleared-workload'));
  http.request = original;

  const component = load(`${legacy}container-target-item.vue`);
  const oldPending = [];
  const context = Object.assign(component.data.call({ $t: text => text }), {
    typeListIDStrList: ['Deployment'],
    bkBizId: 2,
    bcsClusterId: 'cluster',
    conItem: config,
    formData: { workload_type: 'Deployment' },
    $http: { request: (name, args) => new Promise(resolve => oldPending.push({ query: args.query, resolve })) },
  });
  context.getWorkLoadNameList = component.methods.getWorkLoadNameList.bind(context);
  context.getWorkLoadNameList();
  config.noQuestParams.namespacesExclude = '!=';
  component.watch.namespaceScope.handler.call(context);
  await flush();
  oldPending.at(-1).resolve({ code: 0, data: ['current'] });
  await flush();
  oldPending[0].resolve({ code: 0, data: ['old'] });
  await flush();
  assert.deepEqual(plain(context.nameList), [{ id: 'current', name: 'current' }]);
}
