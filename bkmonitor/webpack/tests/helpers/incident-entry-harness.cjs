const fs = require('node:fs');
const path = require('node:path');
const { createRequire } = require('node:module');
const ts = require('typescript');
const babel = require('@babel/core');
const vueJsx = require('@vue/babel-plugin-jsx');
const vue = createRequire(path.resolve(__dirname, '../../src/trace/package.json'))('vue');

const source = path.resolve(__dirname, '../../src/trace/pages/failure');

function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((yes, no) => {
    resolve = yes;
    reject = no;
  });
  return { promise, resolve, reject };
}

async function flush() {
  for (let i = 0; i < 12; i++) {
    await Promise.resolve();
    await vue.nextTick();
  }
}

function panels(topoEnabled = true) {
  return {
    status: 'finished',
    panels: {
      incident_topology: { enabled: topoEnabled },
      incident_alerts: { enabled: true },
      incident_diagnosis: { enabled: false, sub_panels: {} },
    },
  };
}

function loadComponent(file, imports) {
  const javascript = ts.transpileModule(fs.readFileSync(path.join(source, file), 'utf8'), {
    compilerOptions: {
      module: ts.ModuleKind.ESNext,
      target: ts.ScriptTarget.ES2020,
      jsx: ts.JsxEmit.Preserve,
    },
  }).outputText;
  const rendered = babel.transformSync(javascript, {
    filename: file.replace(/\.tsx$/, '.jsx'),
    configFile: false,
    babelrc: false,
    plugins: [vueJsx],
  }).code;
  const output = ts.transpileModule(rendered, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
  }).outputText;
  const module = { exports: {} };
  const requireBoundary = name => {
    if (name === 'vue') return vue;
    if (name === 'vue-i18n') return { useI18n: () => ({ t: value => value }) };
    if (name.endsWith('.scss')) return {};
    if (Object.hasOwn(imports, name)) return imports[name];
    throw new Error(`Unstubbed dependency: ${name}`);
  };
  new Function('require', 'module', 'exports', 'h', 'window', output)(requireBoundary, module, module.exports, vue.h, {
    i18n: { t: value => value },
  });
  return module.exports.default;
}

function element(type, text = '') {
  return { type, text, children: [], parent: null, props: {} };
}

// Only the host renderer and unrelated UI/API boundaries are replaced. The two
// production components retain their setup, render, lifecycle and watchers.
function createHarness(options = {}) {
  const calls = { api: [], replace: [], warnings: [] };
  const route = vue.reactive({
    name: 'incident-detail',
    params: { id: options.id || '1700000000000001' },
    query: { from: 'now-7d', to: 'now', fromPage: 'alarm-center', ...options.query },
  });
  const contentMounted = vue.ref(options.mountContent !== false);
  const router = {
    async replace(target) {
      calls.replace.push(structuredClone(target));
      if (target.params && options.routeReady) await options.routeReady;
      if (target.params) route.params = { ...target.params };
      if (target.query) route.query = { ...target.query };
    },
  };
  const ui = name => vue.defineComponent({ name, render: () => vue.h(name) });
  const empty = ui('UnrelatedPanel');
  const boundary = name => ({ default: ui(name) });
  const api = {
    getIncidentDocId: async params => {
      calls.api.push({ name: 'resolve', params });
      return options.resolveId ? await options.resolveId : { id: options.docId || '1700000000000001' };
    },
    incidentDetail: async params => {
      calls.api.push({ name: 'detail', params });
      return options.detail || { id: params.id, incident_id: '42', current_snapshot: { bk_biz_ids: [] } };
    },
    incidentResults: async params => {
      calls.api.push({ name: 'results', params });
      return options.results ? await options.results : panels();
    },
    incidentOperations: async () => [],
    incidentOperationTypes: async () => [],
    incidentValidateQueryString: async () => ({ result: true }),
  };
  const content = loadComponent('failure-content/failure-content.tsx', {
    'bkui-vue': { Checkbox: empty },
    'monitor-api/modules/incident': api,
    '../alarm-detail/alarm-detail': boundary('AlarmDetail'),
    '../failure-handle/filter-search-input': boundary('FilterSearchInput'),
    '../failure-menu/failure-menu': boundary('FailureMenu'),
    '../failure-topo/failure-topo': boundary('FailureTopo'),
    '../failure-view/failure-view': boundary('FailureView'),
    '../utils': { replaceSpecialCondition: value => value },
  });
  const layout = vue.defineComponent({
    inheritAttrs: false,
    setup(_, { slots }) {
      return () => {
        return vue.h('Layout', [slots?.aside?.(), contentMounted.value ? slots?.main?.() : null]);
      };
    },
  });
  const wrapper = loadComponent('failure.tsx', {
    'bkui-vue': { Loading: ui('Loading'), ResizeLayout: layout },
    dayjs: { default: () => ({ unix: () => 1700000000 }) },
    'monitor-api/modules/alert': {
      alertTopN: async () => ({ fields: [], doc_count: 0 }),
      listAlertTags: async () => [],
    },
    'monitor-api/modules/incident': api,
    'monitor-common/utils': { docCookies: { getItem: () => 'zh' }, LANGUAGE_COOKIE_KEY: 'lang' },
    'vue-router': { useRoute: () => route, useRouter: () => router },
    '../alarm-center/alarm-detail/alarm-detail-sideslider': boundary('AlarmCenterDetail'),
    './failure-content/failure-content': { default: content },
    './failure-header/failure-header': boundary('FailureHeader'),
    './failure-nav/failure-nav': boundary('FailureNav'),
    './failure-tags/failure-tags': boundary('FailureTags'),
    './failure-process/process': { replaceStr: value => value, typeTextMap: {} },
    './utils': { useIncidentProvider: () => {} },
    './composables/use-alarm-detail': {
      useIncidentAlarmDetail: () => ({
        updateAlarmDetailShow: () => {},
        alarmDetailShow: vue.ref(false),
        alarmDetailData: vue.ref({}),
      }),
    },
  });
  const renderer = vue.createRenderer({
    createElement: element,
    createText: text => element('text', text),
    createComment: text => element('comment', text),
    setText: (node, text) => {
      node.text = text;
    },
    setElementText: (node, text) => {
      node.text = text;
      node.children = [];
    },
    parentNode: node => node.parent,
    nextSibling: node => node.parent?.children[node.parent.children.indexOf(node) + 1] || null,
    patchProp: (node, key, _, value) => {
      node.props[key] = value;
    },
    insert(node, parent, anchor = null) {
      if (node.parent) node.parent.children.splice(node.parent.children.indexOf(node), 1);
      const index = anchor ? parent.children.indexOf(anchor) : -1;
      if (index < 0) parent.children.push(node);
      else parent.children.splice(index, 0, node);
      node.parent = parent;
    },
    remove(node) {
      if (node.parent) node.parent.children.splice(node.parent.children.indexOf(node), 1);
      node.parent = null;
    },
  });
  const app = renderer.createApp(wrapper, { id: route.params.id });
  app.config.warnHandler = message => calls.warnings.push(message);
  const root = element('root');
  const vm = app.mount(root);
  return { vm, route, calls, contentMounted, root, unmount: () => app.unmount() };
}

module.exports = { createHarness, deferred, flush, panels };
