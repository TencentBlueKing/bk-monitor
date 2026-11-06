const fs = require('node:fs');
const path = require('node:path');
const { createRequire } = require('node:module');
const ts = require('typescript');
const babel = require('@babel/core');
const vueJsx = require('@vue/babel-plugin-jsx');
const vue = createRequire(path.resolve(__dirname, '../../src/trace/package.json'))('vue');
const { renderToString } = createRequire(path.resolve(__dirname, '../../src/trace/package.json'))(
  'vue/server-renderer'
);
const base = path.resolve(__dirname, '../../src/trace/pages/failure/failure-topo');

function load(file, imports = {}) {
  const filename = path.resolve(base, file);
  let code = ts.transpileModule(fs.readFileSync(filename, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2020, jsx: ts.JsxEmit.Preserve },
  }).outputText;
  if (filename.endsWith('.tsx')) {
    code = babel.transformSync(code, {
      filename: filename.replace(/\.tsx$/, '.jsx'),
      configFile: false,
      babelrc: false,
      plugins: [vueJsx],
    }).code;
  }
  code = ts.transpileModule(code, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
  }).outputText;
  const module = { exports: {} };
  const boundary = name => {
    if (name === 'vue') return vue;
    if (name === 'vue-i18n') return { useI18n: () => ({ t: value => value }) };
    if (name.endsWith('.scss')) return {};
    if (Object.hasOwn(imports, name)) return imports[name];
    if (name.startsWith('.')) return load(path.relative(base, path.resolve(path.dirname(filename), name + '.ts')));
    throw new Error(`Unstubbed dependency: ${name}`);
  };
  new Function('require', 'module', 'exports', code)(boundary, module, module.exports);
  return module.exports;
}

const relations = load('edge-relation.ts');

// Execute the production G6 edge callback. Only the graphics primitive is replaced;
// no style/classification logic is reproduced in the harness.
function drawingCallback(file) {
  const source = ts.createSourceFile(
    file,
    fs.readFileSync(path.resolve(base, file), 'utf8'),
    ts.ScriptTarget.Latest,
    true
  );
  const callbacks = [];
  function visit(node) {
    if (
      ts.isCallExpression(node) &&
      ts.isPropertyAccessExpression(node.expression) &&
      node.expression.expression.getText(source) === 'graph' &&
      node.expression.name.text === 'edge'
    ) {
      callbacks.push(node.arguments[0].getText(source));
    }
    ts.forEachChild(node, visit);
  }
  visit(source);
  if (callbacks.length !== 1) throw new Error(`Expected one production edge callback in ${file}`);
  const code = ts.transpileModule(`const draw = ${callbacks[0]};`, {
    compilerOptions: { target: ts.ScriptTarget.ES2020 },
  }).outputText;
  return new Function('isDirectedEdge', 'Arrow', `${code}; return draw;`)(relations.isDirectedEdge, {
    triangle: (width, height, offset) => ['triangle', width, height, offset],
  });
}

const drawMain = drawingCallback('composables/use-topo-graph.ts');
const drawResource = drawingCallback('../resource-graph/resource-graph.tsx');

function animationStarts(edge) {
  const filename = path.join(base, 'graph/topo-edge.ts');
  const source = ts.createSourceFile(filename, fs.readFileSync(filename, 'utf8'), ts.ScriptTarget.Latest, true);
  let method;
  function visit(node) {
    if (ts.isMethodDeclaration(node) && node.name.getText(source) === 'handleEdgeAnimation')
      method = node.getText(source);
    ts.forEachChild(node, visit);
  }
  visit(source);
  if (!method) throw new Error('Production animation method missing');
  const code = ts.transpileModule(`const handler = { ${method} };`, {
    compilerOptions: { target: ts.ScriptTarget.ES2020 },
  }).outputText;
  let scheduled = 0;
  const invoke = new Function(
    'isDirectedEdge',
    'setInterval',
    'clearInterval',
    `let edgeInterval = []; ${code}; return handler.handleEdgeAnimation;`
  )(
    relations.isDirectedEdge,
    () => ++scheduled,
    () => {}
  );
  invoke({}, {}, edge);
  return scheduled;
}

const empty = vue.defineComponent({ render: () => null });
const edgeInfo = load('detail/edge-info.tsx', {
  'bkui-vue': {
    OverflowTitle: vue.defineComponent({
      setup:
        (_, { slots }) =>
        () =>
          vue.h('span', slots.default?.()),
    }),
  },
  '../../utils': { checkIsRoot: () => false },
  '../node-type-svg': { NODE_TYPE_ICON: {} },
  '../utils': { canJumpByType: () => false, getApmServiceType: () => 'APMService', handleToLink() {} },
  './metric-view': { default: empty },
  './snapshot-analysis-info': { default: empty },
}).default;
const edgeList = load('tooltip/aggregated-edges-list.tsx').default;

function withNodes(edge) {
  return {
    ...edge,
    nodes: ['source', 'target'].map(side => ({
      entity: {
        entity_id: edge[side] || side,
        entity_name: edge[`${side}_name`] || side,
        entity_type: 'APMService',
      },
    })),
  };
}

async function renderEdge(edge) {
  return renderToString(
    vue.createSSRApp({
      setup() {
        vue.provide('bkzIds', vue.ref(['1']));
        vue.provide('incidentDetail', vue.ref({}));
        return () => vue.h(edgeInfo, { activeEdge: withNodes(edge) });
      },
    })
  );
}

async function renderList(edge) {
  return renderToString(vue.createSSRApp({ render: () => vue.h(edgeList, { edge, onClick() {} }) }));
}

async function readMetrics(edge) {
  const requests = [];
  const hookModule = load('detail/useMetrics.ts', {
    'monitor-api/modules/incident': {
      incidentMetricsSearch: async params => {
        requests.push(['metrics', params]);
        throw new Error('Unexpected live query');
      },
      incidentEventsSearch: async params => {
        requests.push(['events', params]);
        throw new Error('Unexpected live query');
      },
    },
    '../utils': { handleEndTime: (start, end) => end, scaleArrayToRange: value => value },
    'monitor-ui/monitor-echarts/types/monitor-echarts': { echarts: { disconnect() {}, connect() {} } },
    'throttle-debounce': { debounce: (_delay, fn) => fn },
  }).default;
  let hook;
  const app = vue.createSSRApp({
    setup() {
      hook = hookModule(
        vue.ref({}),
        vue.ref(edge.edge_type),
        vue.ref(-1),
        vue.ref(false),
        () => {},
        vue.ref(edge.events || []),
        vue.ref(edge.graph_analysis)
      );
      return () => null;
    },
  });
  app.provide('incidentDetail', vue.ref({ begin_time: 1700000000, end_time: 1700000600 }));
  await renderToString(app);
  await hook.getMetricsData();
  await hook.getEventsData();
  return {
    metrics: JSON.parse(JSON.stringify(hook.metricsData.value)),
    requests,
    exception: { ...hook.exceptionData.value },
  };
}

async function renderNode(model, nodeActiveTab = 'metric', linkedEdges = []) {
  let metricInput;
  let nodeState;
  let headerTree;
  const emitted = [];
  const component = load('detail/node-info.tsx', {
    'bkui-vue': { Message() {}, OverflowTitle: empty },
    'monitor-common/utils/utils': { copyText() {} },
    '../../utils': { checkIsRoot: () => false },
    '../node-type-svg': { NODE_TYPE_ICON: {} },
    '../tooltip/aggregated-edges-list': { default: edgeList },
    '../utils': {
      canJumpByType: () => false,
      getApmServiceType: () => 'APMService',
      handleToLink() {},
      truncateText: text => text,
      typeToLinkHandle: {},
    },
    './metric-view': {
      default: vue.defineComponent({
        props: ['data'],
        setup(props) {
          metricInput = props.data;
          return () => vue.h('div', { class: 'metric-view-boundary' });
        },
      }),
    },
    './snapshot-analysis-info': { default: load('detail/snapshot-analysis-info.tsx').default },
  }).default;
  const setup = component.setup;
  component.setup = (props, context) => {
    nodeState = setup(props, context);
    const renderNodeInfo = nodeState.renderNodeInfo;
    nodeState.renderNodeInfo = node => {
      headerTree = renderNodeInfo(node);
      return headerTree;
    };
    return nodeState;
  };
  const app = vue.createSSRApp({
    setup() {
      vue.provide('bkzIds', vue.ref(['1']));
      vue.provide('incidentDetail', vue.ref({}));
      return () =>
        vue.h(component, {
          model,
          nodeActiveTab,
          linkedEdges,
          showViewResource: false,
          onToDetailSlider: node => emitted.push(['alert', node]),
          onShowEdgeDetail: edge => emitted.push(['edge', edge]),
        });
    },
  });
  for (const name of ['overflow-tips', 'bk-tooltips']) app.directive(name, {});
  const html = await renderToString(app);
  function find(vnode, className) {
    if (vnode?.props?.class === className) return vnode;
    if (Array.isArray(vnode?.children)) {
      for (const child of vnode.children) {
        const found = find(child, className);
        if (found) return found;
      }
    }
  }
  return {
    html,
    metricInput,
    emitted,
    clickAlert: () => find(headerTree, 'flex-label').props.onClick(),
    clickEdge: edge => nodeState.showEdgeDetail(edge),
  };
}

module.exports = {
  relations,
  drawMain,
  drawResource,
  animationStarts,
  renderEdge,
  renderList,
  readMetrics,
  renderNode,
};
