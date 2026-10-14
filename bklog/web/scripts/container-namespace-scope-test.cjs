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
        timers.set(++timerId, callback);
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
        throw new Error('Unsupported boundary: ' + name);
      },
    },
    { filename },
  );
  return module.exports.default;
}

function load(file) {
  const filename = path.join(root, file);
  const source = process.argv.includes('--baseline')
    ? execFileSync('git', ['show', 'upstream/master:bklog/web/' + file], { encoding: 'utf8' })
    : fs.readFileSync(filename, 'utf8');
  return evaluate(file.endsWith('.vue') ? compiler.parseComponent(source).script.content : source, filename);
}
function setup(file, props) {
  const scope = Vue.effectScope();
  scopes.push(scope);
  return scope.run(() => load(file).setup(props, { emit: () => {} }));
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
    current + 'workload-selection.tsx',
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

  const editRender = setup(current + 'config-log-set-edit-item.tsx', {
    config,
    bcsClusterId: 'cluster',
    isNode: false,
    editType: 'label_selector',
    clusterList: [],
  });
  const labelParams = find(editRender(), node => node.tag === './label-choose-dialog').props.labelParams;
  assert.equal(labelParams.namespacesExclude, '!=');
  const labelProps = Vue.reactive({ labelParams, clusterList: [], isShowDialog: false });
  setup(current + 'label-choose-dialog.tsx', labelProps);
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

  const previewRender = setup(current + 'config-cluster-box.tsx', {
    config,
    bcsClusterId: 'cluster',
    isNode: false,
    clusterList: [],
    nameSpacesSelectList: [],
  });
  let tree = previewRender();
  let preview = find(tree, node => node.tag === './config-view-dialog').props.viewQueryParams;
  assert.deepEqual(plain(preview.namespaces_exclude), ['system']);
  assert.ok(!('namespaces' in preview));
  assert.equal(preview.container.container_name_exclude, 'sidecar');
  assert.ok(!('container_name' in preview.container));
  assert.deepEqual(plain(find(tree, node => node.tag === 'bk-tag-input').props.value), ['sidecar']);
  const previewProps = Vue.reactive({ isShowDialog: false, viewQueryParams: preview });
  setup(current + 'config-view-dialog.tsx', previewProps);
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

  const oldWorkload = load(legacy + 'container-target-item.vue');
  const oldContext = {
    conItem: config,
    typeListIDStrList: ['Deployment'],
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

  const oldLabels = load(legacy + 'label-target-dialog.vue');
  const oldLabelContext = {
    labelParams: { ...labelParams },
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

  const oldConfigs = load(legacy + 'configs-select.vue');
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
  const save = evaluate('export default ' + saveExpression, saveFile, {
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
  saved = save({}, [config], false, false, [], 'cluster').configs[0];
  assert.deepEqual(plain(saved.namespaces), ['system']);
  assert.ok(!('namespaces_exclude' in saved));

  scopes.forEach(scope => scope.stop());
  console.log(
    'container-namespace-scope-test: passed (real component code, mocked HTTP / UI; no browser or live backend)',
  );
}
main().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
