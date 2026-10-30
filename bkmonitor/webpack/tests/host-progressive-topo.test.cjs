const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');
const ts = require('typescript');
const { serviceHarness } = require('./helpers/host-service-harness.cjs');

const vue = require('../src/trace/node_modules/vue');

const root = path.join(__dirname, '../src/trace/pages/host');
const flush = async () => {
  await new Promise(resolve => setImmediate(resolve));
  await vue.nextTick();
};
const host = id => ({
  bk_host_id: id,
  bk_biz_id: 1,
  bk_host_name: `host-${id}`,
  bk_host_innerip: `127.0.0.${id}`,
  bk_cloud_id: 0,
  module: [],
});
const leaf = id => ({ ...host(id), id: String(id), ip: `127.0.0.${id}` });
const inst = (id, children = []) => ({
  id,
  name: id,
  bk_obj_id: id.split('|')[0],
  bk_inst_id: Number(id.split('|')[1]),
  children,
});
const skeleton = () => [inst('biz|1', [inst('set|2', [inst('module|3'), inst('module|4')])])];
const fullTree = () => [inst('biz|1', [inst('set|2', [inst('module|3', [leaf(11), leaf(12)]), inst('module|4')])])];

function harness(query = {}, readonly = false, workerResponse, requestOwner, bizId = 1, requestBoundary = false) {
  global.window = { cc_biz_id: bizId, timezone: 'UTC', i18n: { t: value => value }, rawWindow: requestOwner };
  if (requestBoundary) global.window.enable_cmdb_level = true;
  global.ResizeObserver = class {
    observe() {}
    disconnect() {}
  };
  const route = vue.reactive({ query, params: {}, fullPath: '/' });
  const appStore = vue.reactive({ bizId });
  const store = vue.reactive({
    scene: 'host',
    nodeId: '',
    activeTab: '',
    timeRange: ['old', 'old'],
    timezone: '',
    refreshInterval: -1,
    refreshGeneration: 0,
    timeRangeTimestamp: { start_time: 100, end_time: 200 },
    refreshImmediate: false,
    where: [],
    keyword: '',
    filterExpanded: false,
    activeCategory: '',
    metricAggregationState: { compareType: 'target', compareTargets: [] },
    processMetricAggregationState: { compareType: 'none', compareTargets: [], columns: 2 },
    hostProcessName: '',
    hostProcessKeyword: '',
  });
  const calls = [];
  const http = requestBoundary ? serviceHarness(requestOwner, { cc_biz_id: bizId }) : null;
  const services = http?.api || Object.fromEntries(
    [
      'getHostInfoPage',
      'getHostInfoList',
      'getHostMetricInfoList',
      'getHostMetricStats',
      'getHostTopoTreeByBizId',
      'getHostProcessList',
      'getHostProcessUptime',
    ].map(name => [name, (...args) => new Promise((resolve, reject) => calls.push({ name, args, resolve, reject }))])
  );
  const chartTargets = [];
  const chartRequests = [];
  let processTable,
    detail,
    formatShare,
    header,
    statCards,
    restores = 0,
    table,
    topo;
  const listSend = rawWorker('host-list');
  const listWorker = {
    initBaseData: baseList => Promise.resolve(listSend({ type: 'INIT_BASE', baseList })),
    mergeMetrics: metricListMap => Promise.resolve(listSend({ type: 'MERGE_METRICS', metricListMap })),
    compute: params => Promise.resolve(listSend({ type: 'COMPUTE', params })),
  };
  const empty = vue.defineComponent({ setup: () => () => null });
  const Button = vue.defineComponent({
    setup:
      (_, { attrs, slots }) =>
      () =>
        vue.h('button', attrs, slots.default?.()),
  });
  const Input = vue.defineComponent({
    setup:
      (_, { attrs }) =>
      () =>
        vue.h('input', attrs),
  });
  const layout = vue.defineComponent({
    setup:
      (_, { slots }) =>
      () =>
        vue.h('section', [slots.main?.(), slots.aside?.()]),
  });
  const Table = vue.defineComponent({
    setup:
      (_, { attrs }) =>
      () => {
        table = attrs;
        return vue.h(
          'table',
          (attrs.data || []).map(row => vue.h('tr', { key: row.rowId }, row.bk_host_innerip))
        );
      },
  });
  const ProcessTable = vue.defineComponent({
    setup:
      (_, { attrs }) =>
      () => {
        processTable = attrs;
        return null;
      },
  });
  const Sideslider = vue.defineComponent({
    setup:
      (_, { attrs, slots }) =>
      () =>
        attrs.isShow ? slots.default?.() : null,
  });
  const metricGroups = () => ({
    submitting: vue.shallowRef(false),
    load: async () => {},
    settingShow: vue.shallowRef(false),
    loadError: vue.shallowRef(false),
    loading: vue.shallowRef(false),
    rows: vue.shallowRef([]),
    orderData: vue.shallowRef([]),
  });
  const cache = new Map();
  const own =
    /(?:host\.tsx|host-content-tabs\.tsx|host-list\.tsx|host-topo-tree\.tsx|host-process\.tsx|host-metric\.tsx|process-detail\.tsx|use-process-list\.ts|process-service\.ts|host-request\.ts|use-metric-aggregation\.ts|constants\/process\.ts|utils\/process\.ts|variables\/resolve\.ts|use-host-topo-tree\.ts|use-host-url-params\.ts|use-host-list\.ts|use-host-list-data\.ts|host-list-core\.ts|share-scope\.ts|topo-tree\.ts|constants\/enum\.ts|constants\/constants\.ts)$/;
  const load = file => {
    if (cache.has(file)) return cache.get(file);
    const module = { exports: {} };
    cache.set(file, module.exports);
    const dependency = id => {
      if (id === 'vue') return vue;
      if (id === 'vue-router')
        return { useRoute: () => route, useRouter: () => ({ resolve: () => ({ fullPath: '/' }), replace() {} }) };
      if (id === 'pinia') return { storeToRefs: vue.toRefs };
      if (id === 'vue-i18n') return { useI18n: () => ({ t: value => value }) };
      if (id === 'monitor-api/cancel') return { CancelToken: class {} };
      if (id === 'monitor-common/utils/equal') return { arraysEqual: (a, b) => JSON.stringify(a) === JSON.stringify(b) };
      if (id === 'monitor-ui/chart-plugins/constants/charts') return { COLOR_LIST: [], COLOR_LIST_BAR: [] };
      if (id === 'monitor-ui/monitor-echarts/valueFormats/valueFormats') return { getValueFormat: () => () => ({}) };
      if (id === './use-chart-view-option') return { useChartViewOption: () => ({ watchHighlightPeak() {} }) };
      if (id === './use-chart-tooltips') return {};
      if (id === '@/common/embed-context') return { withEmbedQuery: value => value };
      if (id === '@/pages/host/components/dashbords/variables/resolve')
        return load(`${root}/components/dashbords/variables/resolve.ts`);
      if (id === '@vueuse/core') return { useDebounceFn: fn => fn };
      if (id === 'bkui-vue')
        return {
          ResizeLayout: layout,
          Sideslider,
          Exception: empty,
          Alert: empty,
          Button,
          Input,
          Checkbox: Input,
          Message() {},
        };
      if (id.endsWith('/provider')) return { useAppReadonlyInject: () => readonly };
      if (id.endsWith('/store/modules/host')) return { useHostStore: () => store };
      if (id.endsWith('/store/modules/app')) return { useAppStore: () => appStore };
      if (id.endsWith('/use-host-topo-tree-worker')) return { useHostTopoTreeWorker: () => treeClient(workerResponse) };
      if (id.endsWith('/use-host-list-worker')) return { useHostListWorker: () => listWorker };
      if (id.endsWith('/host-service')) return services;
      if (requestBoundary && id.endsWith('/common-header/common-header'))
        return {
          default: vue.defineComponent({
            setup: (_, { attrs, slots }) => () => {
              header = attrs;
              return vue.h('header', [slots.left?.(), slots.accessGuide?.()]);
            },
          }),
        };
      if (requestBoundary && id.endsWith('/host-location-bar/host-location-bar'))
        return load(`${root}/components/host-location-bar/host-location-bar.tsx`);
      if (requestBoundary && id.endsWith('/temporary-share/temporary-share'))
        return {
          default: vue.defineComponent({
            setup: (_, { attrs }) => () => {
              formatShare = attrs.formatTokenParams;
              return null;
            },
          }),
        };
      if (id === 'monitor-api/modules/scene_view') return services;
      if (id.endsWith('/process-table')) return { default: ProcessTable };
      if (id.endsWith('/use-metric-groups')) return { useMetricGroups: metricGroups };
      if (id.endsWith('/use-process-metric')) return { useProcessMetric: metricGroups };
      if (id.endsWith('/dashbords')) {
        const variables = load(`${root}/components/dashbords/variables/resolve.ts`);
        return {
          ...variables,
          DashboardPanel: vue.defineComponent({
            setup: (_, { attrs }) => {
              if (requestBoundary) {
                const panel = vue.computed(() => variables.resolveGraphPanel({
                  id: 'cpu',
                  targets: [{
                    apiModule: 'grafana',
                    apiFunc: 'graphUnifyQuery',
                    data: { query_configs: [{ filter_dict: { targets: ['$current_target', '$compare_targets'] } }] },
                  }],
                }, attrs.scopedVars));
                load(path.join(root, '../trace-explore/components/explore-chart/use-echarts.ts')).useEcharts({
                  panel,
                  chartRef: vue.shallowRef(null),
                  params: {},
                  customOptions: {},
                  $api: { grafana: { graphUnifyQuery: params => {
                    chartRequests.push({ params, bizId: appStore.bizId });
                    return Promise.resolve({ series: [], metrics: [] });
                  } } },
                });
              }
              return () => {
                chartTargets.push(
                  variables.resolveVariables({ targets: ['$current_target', '$compare_targets'] }, attrs.scopedVars)
                    .targets
                );
                return null;
              };
            },
          }),
        };
      }
      if (id === 'lodash') return { cloneDeep: structuredClone };
      if (id === 'dayjs') return { default: require('dayjs') };
      if (id.endsWith('/template-srv')) return { getTemplateSrv: () => ({ replace: value => value }) };
      if (id === 'monitor-ui/chart-plugins/typings')
        return {
          PanelModel: class {
            constructor(value) {
              Object.assign(this, value);
            }
          },
        };
      if (requestBoundary && id.endsWith('/use-host-detail'))
        return {
          useHostDetail: (...args) => (detail = load(`${root}/composables/use-host-detail.ts`).useHostDetail(...args)),
        };
      if (id.endsWith('/use-host-detail'))
        return { useHostDetail: () => ({ detailData: vue.shallowRef([]), loading: vue.shallowRef(false) }) };
      if (id.endsWith('/host-list-table')) return { default: Table };
      if (requestBoundary && id.endsWith('/host-stat-cards'))
        return {
          default: vue.defineComponent({
            setup: (_, { attrs }) => () => {
              statCards = attrs;
              return null;
            },
          }),
        };
      if (id.endsWith('/host-list-toolbar') || id.endsWith('/host-list-filter') || id.endsWith('/host-stat-cards'))
        return { default: empty };
      if (id.endsWith('/useUserConfig'))
        return { default: () => ({ handleGetUserConfig: async () => ({}), handleSetUserConfig: async () => {} }) };
      if (id.endsWith('/use-table-columns-cache'))
        return { useTableColumnsCache: () => ({ storageColumns: vue.shallowRef([]), fieldsWidthConfig: {} }) };
      if (id.endsWith('/time-range/utils')) return { handleTransformToTimestamp: range => range.map(Number) };
      if (id === 'monitor-common/utils')
        return {
          isObject: value => !!value && typeof value === 'object',
          random: () => 'chart',
          commonPageSizeGet: () => 100,
          parseBizId: Number,
          tryURLDecodeParse: (value, fallback) => {
            try {
              return JSON.parse(decodeURIComponent(value));
            } catch {
              return fallback;
            }
          },
        };
      if (id === 'monitor-common/utils/utils') return {};
      if (id === 'monitor-common/utils/host-monitor-url')
        return load(path.join(__dirname, '../src/monitor-common/utils/host-monitor-url.ts'));
      if (id.endsWith('/retrieval-filter/typing')) return { EMode: { ui: 'ui' }, EFieldType: {} };
      if (id.endsWith('/across-page-selection')) return { SelectType: {} };
      if (id.endsWith('/constants/host-list'))
        return { HOST_FILTER_FIELDS: [], HOST_LIST_COLUMNS: [], HOST_LIST_DEFAULT_PAGE_SIZE: 100, NUMBER_METHODS: [] };
      if (id.endsWith('/constants/aggregation')) return { DEFAULT_AGGREGATION_STATE: {} };
      if (/\.scss$/.test(id)) return {};
      const resolved = path.resolve(path.dirname(file), id);
      for (const ext of ['.ts', '.tsx'])
        if (own.test(resolved + ext) && fs.existsSync(resolved + ext)) return load(resolved + ext);
      return { default: empty };
    };
    const code = ts.transpileModule(fs.readFileSync(file, 'utf8'), {
      fileName: file,
      compilerOptions: {
        target: ts.ScriptTarget.ES2022,
        module: ts.ModuleKind.CommonJS,
        jsx: ts.JsxEmit.React,
        jsxFactory: 'h',
      },
    }).outputText;
    const h = (type, props, ...children) =>
      vue.h(
        type,
        props,
        props?.['v-slots'] ||
          (children.length === 1 && typeof children[0] === 'object' && !vue.isVNode(children[0])
            ? children[0]
            : children)
      );
    new Function('require', 'module', 'exports', 'h', code)(dependency, module, module.exports, h);
    if (file.endsWith('/host-topo-tree.tsx')) {
      const setup = module.exports.default.setup;
      module.exports.default.setup = (props, context) => {
        topo = props.context;
        return setup(props, context);
      };
    }
    if (file.endsWith('/use-host-url-params.ts')) {
      const actual = module.exports.useHostUrlParams;
      module.exports.useHostUrlParams = () => {
        const value = actual();
        const restore = value.getUrlParams;
        value.getUrlParams = () => {
          restores++;
          restore();
        };
        return value;
      };
    }
    cache.set(file, module.exports);
    return module.exports;
  };
  const app = renderer().createApp(load(`${root}/host.tsx`).default);
  app.config.warnHandler = () => {};
  const element = { type: 'root', children: [], props: {} };
  app.mount(element);
  const pending = (name, predicate = () => true) =>
    calls.find(call => !call.done && call.name === name && predicate(call.args));
  const respond = (name, result, predicate, failure = false) => {
    const call = pending(name, predicate);
    assert.ok(call, name);
    call.done = true;
    call[failure ? 'reject' : 'resolve'](result);
  };
  return {
    element,
    appStore,
    route,
    app,
    calls,
    store,
    chartTargets,
    chartRequests,
    http,
    get detail() { return detail; },
    get formatShare() { return formatShare; },
    get header() { return header; },
    get statCards() { return statCards; },
    get processTable() {
      return processTable;
    },
    get topo() {
      return topo;
    },
    get table() {
      return table;
    },
    get restores() {
      return restores;
    },
    pending,
    respond,
    load,
  };
}
function rawWorker(file) {
  let output;
  const self = {
    postMessage: value => {
      output = structuredClone(value);
    },
  };
  vm.runInNewContext(fs.readFileSync(`${root}/workers/${file}.worker.raw.js`, 'utf8'), { self });
  let requestId = 0;
  return message => {
    self.onmessage({ data: structuredClone({ ...message, requestId: ++requestId }) });
    return output;
  };
}
function renderer() {
  const element = type => ({ type, children: [], props: {}, parent: null, clientHeight: 640, scrollTop: 0 });
  return vue.createRenderer({
    createElement: element,
    createText: text => ({ ...element('#text'), text }),
    createComment: text => ({ ...element('#comment'), text }),
    insert(child, parent, anchor = null) {
      if (child.parent) this.remove(child);
      child.parent = parent;
      const at = anchor ? parent.children.indexOf(anchor) : -1;
      parent.children.splice(at < 0 ? parent.children.length : at, 0, child);
    },
    remove(child) {
      const siblings = child.parent?.children;
      if (siblings) siblings.splice(siblings.indexOf(child), 1);
      child.parent = null;
    },
    setText(node, text) {
      node.text = text;
    },
    setElementText(node, text) {
      node.text = text;
    },
    parentNode: node => node.parent,
    nextSibling: node => node.parent?.children[node.parent.children.indexOf(node) + 1],
    patchProp(node, key, old, value) {
      node.props[key] = value;
    },
  });
}

function treeClient(workerResponse = value => Promise.resolve(value)) {
  const send = rawWorker('host-topo-tree');
  return {
    init: (
      treeData,
      hideEmptyNode,
      searchValue,
      selectedId,
      complete = true,
      preserve = false,
      anchorId = '',
      fallbackToRoot = false
    ) =>
      workerResponse(
        send({
          type: preserve ? 'REPLACE' : 'INIT',
          treeData,
          hideEmptyNode,
          searchValue,
          selectedId,
          complete,
          anchorId,
          fallbackToRoot,
        })
      ),
    select: id => workerResponse(send({ type: 'SELECT', id })),
    getRange: (start, end) => workerResponse(send({ type: 'GET_RANGE', start, end })),
    toggle: (id, expanded, start, end) => Promise.resolve(send({ type: 'TOGGLE', id, expanded, start, end })),
    setFilter: (hideEmptyNode, searchValue, start, end) =>
      Promise.resolve(send({ type: 'SET_FILTER', hideEmptyNode, searchValue, start, end })),
    upsertChildren: (parentId, children, page, anchorId = '') =>
      Promise.resolve(send({ type: 'UPSERT_CHILDREN', parentId, children, page, anchorId })),
    expandAll: (start, end) => Promise.resolve(send({ type: 'EXPAND_ALL', start, end })),
    collapseAll: (start, end) => Promise.resolve(send({ type: 'COLLAPSE_ALL', start, end })),
  };
}

test('topology initialization does not mutate a response shared with another consumer', async () => {
  const h = harness({ from: '100', to: '200' });
  const tree = skeleton();
  Object.freeze(tree[0]);
  h.respond('getHostTopoTreeByBizId', tree, args => args[2] === false);
  await flush();
  assert.equal(h.topo.loading.value, false);
  assert.equal(h.topo.loadError.value, false);
  assert.ok(h.topo.visibleRows.value.length > 0);
  assert.equal(tree[0].isOpen, undefined);
  h.app.unmount();
});

test('actual HostPage mounts list before either topology response and restores URL once', async () => {
  const h = harness({ nodeId: 'module|3', from: '100', to: '200', activeTab: 'list' });
  await flush();
  assert.equal(h.restores, 1);
  assert.equal(h.calls.filter(call => call.name === 'getHostInfoPage').length, 1);
  assert.deepEqual(h.pending('getHostInfoPage').args[0], {
    bk_biz_id: 1,
    bk_obj_id: 'module',
    bk_inst_id: 3,
    page: 1,
    page_size: 100,
  });
  h.respond('getHostInfoPage', {
    items: Array.from({ length: 100 }, (_, i) => host(i + 1)),
    page: 1,
    page_size: 100,
    total: 250,
  });
  await flush();
  assert.equal(h.table.data.length, 100);
  assert.equal(h.table.loading, false);
  assert.equal(h.pending('getHostMetricInfoList', ([p]) => p.bk_host_ids?.length === 100).args[0].start_time, 100);
  assert.equal(h.calls.filter(call => call.name === 'getHostTopoTreeByBizId' && !call.done).length, 2);
  h.table.onPageChange(2);
  await flush();
  h.respond('getHostInfoPage', { items: [host(101)], page: 2, page_size: 100, total: 250 });
  await flush();
  h.table.onRowCheck('101', true);
  await flush();
  h.respond('getHostTopoTreeByBizId', skeleton(), args => args[2] === false);
  await flush();
  assert.equal(h.table.page, 2);
  assert.deepEqual([...h.table.selectedRowKeys], ['101']);
  assert.equal(h.calls.filter(call => call.name === 'getHostInfoPage').length, 2);
  h.respond('getHostTopoTreeByBizId', fullTree(), args => args[2] !== false);
  await flush();
  assert.equal(h.table.page, 2);
  assert.deepEqual([...h.table.selectedRowKeys], ['101']);
  assert.equal(h.restores, 1);
  h.app.unmount();
});

test('module pages support loading, more, retry and ignore responses after complete tree', async () => {
  const h = harness();
  await flush();
  h.respond('getHostTopoTreeByBizId', skeleton(), args => args[2] === false);
  await flush();
  await h.topo.handleExpandAll();
  assert.ok(h.topo.visibleRows.value.find(row => row.id === 'module|3'));
  assert.equal(h.topo.visibleRows.value[0].hostCount, null);
  const loading = h.topo.loadModulePage('module|3');
  await flush();
  assert.equal(h.topo.visibleRows.value.find(row => row.loadParentId === 'module|3').loadState, 'loading');
  h.respond('getHostInfoPage', { items: [host(11)], total: 101, page: 1, page_size: 100 }, ([p]) => p.bk_inst_id === 3);
  await loading;
  assert.equal(h.topo.visibleRows.value.find(row => row.loadParentId === 'module|3').loadState, 'more');
  assert.equal(h.topo.visibleRows.value.find(row => row.id === 'module|3').hostCount, 101);
  const failed = h.topo.loadModulePage('module|3');
  await flush();
  h.respond('getHostInfoPage', new Error('fixture'), ([p]) => p.page === 2, true);
  await failed;
  assert.equal(h.topo.visibleRows.value.find(row => row.loadParentId === 'module|3').loadState, 'error');
  const late = h.topo.loadModulePage('module|3');
  await flush();
  h.respond('getHostTopoTreeByBizId', fullTree(), args => args[2] !== false);
  await flush();
  h.respond('getHostInfoPage', { items: [host(99)], total: 101, page: 2, page_size: 100 }, ([p]) => p.page === 2);
  await late;
  assert.equal(h.topo.fullTreeReady.value, true);
  assert.equal(
    h.topo.visibleRows.value.some(row => row.id === '99' || row.loadParentId),
    false
  );
  assert.ok(h.topo.visibleRows.value.some(row => row.id === '12'));
  assert.equal(h.topo.visibleRows.value.find(row => row.id === 'module|3').hostCount, 2);
  assert.equal(
    h.topo.visibleRows.value.some(row => row.id === 'module|4'),
    false
  );
  h.app.unmount();
});

test('invalid share fails closed; host share never requests an empty skeleton or changes to biz', async () => {
  const invalid = harness({ shareTargetType: 'host', shareBkHostId: 'bad' }, true);
  await flush();
  assert.equal(invalid.calls.length, 0);
  invalid.app.unmount();
  const shared = harness({ shareTargetType: 'host', shareBkHostId: '11', nodeId: '999' }, true);
  await flush();
  assert.deepEqual(shared.pending('getHostTopoTreeByBizId').args, [1, { bk_host_id: 11 }]);
  assert.equal(shared.topo.selectedNode.value.bk_host_id, 11);
  shared.respond('getHostTopoTreeByBizId', skeleton());
  await flush();
  assert.equal(shared.topo.selectedNode.value.bk_host_id, 11);
  shared.app.unmount();
});

test('raw Worker upsert deduplicates within a module and replacement preserves expansion/anchor', () => {
  const send = rawWorker('host-topo-tree');
  const tree = skeleton();
  tree[0].isOpen = true;
  const explicit = send({ type: 'INIT', treeData: tree, complete: false, hideEmptyNode: true, selectedId: '999' });
  assert.equal(explicit.selectedNode, null);
  const fallback = send({
    type: 'INIT',
    treeData: skeleton(),
    complete: false,
    hideEmptyNode: true,
    selectedId: 'biz|-5066',
    fallbackToRoot: true,
  });
  assert.equal(fallback.selectedNode.id, 'biz|1');
  send({ type: 'INIT', treeData: tree, complete: false, hideEmptyNode: true, selectedId: '999' });
  const missing = send({ type: 'SELECT', id: '999' });
  assert.equal(missing.selectedNode, null);
  send({ type: 'EXPAND_ALL', start: 0, end: 100 });
  for (let i = 0; i < 2; i++)
    send({ type: 'UPSERT_CHILDREN', parentId: 'module|3', children: [leaf(11)], page: { status: 'more', total: 2 } });
  let rows = send({ type: 'GET_RANGE', start: 0, end: 100 }).rows;
  assert.equal(rows.filter(row => row.id === '11').length, 1);
  const replaced = send({
    type: 'REPLACE',
    treeData: fullTree(),
    complete: true,
    hideEmptyNode: true,
    selectedId: '11',
    anchorId: 'module|3',
  });
  assert.equal(replaced.selectedNode.bk_host_id, 11);
  assert.equal(replaced.anchorOffset, 2);
  rows = send({ type: 'GET_RANGE', start: 0, end: 100 }).rows;
  assert.ok(rows.find(row => row.id === 'module|3').isExpanded);
  assert.equal(
    rows.some(row => row.loadParentId),
    false
  );
});

test('first expansion fetches one module page; background topology failure keeps skeleton and table', async () => {
  const h = harness();
  await flush();
  h.respond('getHostInfoPage', { items: [host(1)], total: 1, page: 1, page_size: 100 });
  h.respond('getHostTopoTreeByBizId', skeleton(), args => args[2] === false);
  await flush();
  const set = h.topo.visibleRows.value.find(row => row.id === 'set|2');
  await h.topo.handleExpandNode(set);
  await flush();
  const module = h.topo.visibleRows.value.find(row => row.id === 'module|3');
  await h.topo.handleExpandNode(module);
  await flush();
  await h.topo.handleExpandNode(module);
  await flush();
  assert.equal(h.calls.filter(call => call.name === 'getHostInfoPage' && call.args[0].bk_inst_id === 3).length, 1);
  h.respond('getHostTopoTreeByBizId', new Error('fixture'), args => args[2] !== false, true);
  await flush();
  assert.equal(h.topo.fullTreeError.value, true);
  assert.equal(h.topo.loadError.value, false);
  assert.equal(h.table.data.length, 1);
  assert.equal(h.table.loading, false);
  h.respond('getHostInfoPage', { items: [], total: 0, page: 1, page_size: 100 }, ([p]) => p.bk_inst_id === 3);
  await flush();
  assert.equal(
    h.topo.visibleRows.value.some(row => row.loadParentId === 'module|3'),
    false
  );
  const pending = h.topo.loadModulePage('module|4');
  await flush();
  const before = h.topo.visibleRows.value;
  h.app.unmount();
  h.respond('getHostInfoPage', { items: [host(50)], total: 1, page: 1, page_size: 100 }, ([p]) => p.bk_inst_id === 4);
  await pending;
  assert.equal(h.topo.visibleRows.value, before);
});

test('complete tree overtakes skeleton and scope parser rejects malformed and cross-business targets', async () => {
  const h = harness({ nodeId: 'module|3' });
  await flush();
  h.respond('getHostTopoTreeByBizId', fullTree(), args => args[2] !== false);
  await flush();
  h.respond('getHostTopoTreeByBizId', skeleton(), args => args[2] === false);
  await flush();
  assert.equal(h.topo.fullTreeReady.value, true);
  await h.topo.handleExpandAll();
  assert.ok(h.topo.visibleRows.value.some(row => row.id === '12'));
  assert.equal(
    h.topo.visibleRows.value.some(row => row.loadParentId),
    false
  );
  const { resolveInitialHostScope } = h.load(`${root}/utils/share-scope.ts`);
  assert.deepEqual(resolveInitialHostScope(false, {}, '', 1), { bk_obj_id: 'biz', bk_inst_id: 1 });
  assert.deepEqual(resolveInitialHostScope(false, {}, '12', 1), { bk_host_id: 12 });
  assert.deepEqual(resolveInitialHostScope(false, {}, 'custom_level|8', 1), {
    bk_obj_id: 'custom_level',
    bk_inst_id: 8,
  });
  for (const id of ['bad', '-1', 'biz|2', 'module|0', 'module|12|extra'])
    assert.equal(resolveInitialHostScope(false, {}, id, 1), null);
  assert.equal(resolveInitialHostScope(true, {}, '', 1), null);
  assert.equal(resolveInitialHostScope(true, { shareTargetType: 'host', shareBkHostId: true }, '', 1), null);
  assert.equal(
    resolveInitialHostScope(true, { shareTargetType: 'topo', shareBkObjId: 'biz', shareBkInstId: 2 }, '', 1),
    null
  );
  // 空间入口：负 spaceId 根别名可用；真实业务根待拓扑确认；其他负根与负数对象 ID 仍拒绝
  assert.deepEqual(resolveInitialHostScope(false, {}, 'biz|-5066', -5066), { bk_obj_id: 'biz', bk_inst_id: -5066 });
  assert.deepEqual(resolveInitialHostScope(false, {}, 'biz|18818', -5066), {
    bk_obj_id: 'biz',
    bk_inst_id: 18818,
    pending: true,
  });
  for (const id of ['biz|-1', 'biz|0', 'set|-2', 'module|-3', '-11', 'biz|-1|2'])
    assert.equal(resolveInitialHostScope(false, {}, id, -5066), null);
  assert.equal(resolveInitialHostScope(false, {}, 'biz|-1', 1), null);
  assert.deepEqual(resolveInitialHostScope(true, {}, 'biz|18818', -5066), {
    bk_obj_id: 'biz', bk_inst_id: 18818, pending: true,
  });
  assert.deepEqual(resolveInitialHostScope(true, {}, 'biz|-5066', -5066), {
    bk_obj_id: 'biz', bk_inst_id: -5066, pending: true,
  });
  assert.deepEqual(
    resolveInitialHostScope(true, { shareTargetType: 'topo', shareBkObjId: 'biz', shareBkInstId: 18818 }, '', -5066),
    { bk_obj_id: 'biz', bk_inst_id: 18818, pending: true }
  );
  h.app.unmount();
});

const SPACE_BIZ = -5066;
const REAL_BIZ = 18818;
const withBiz = node => ({ ...node, bk_biz_id: SPACE_BIZ, ...(node.children ? { children: node.children.map(withBiz) } : {}) });
const spaceSkeleton = () => [withBiz(inst(`biz|${REAL_BIZ}`, [inst('set|2', [inst('module|3'), inst('module|4')])]))];
const spaceFullTree = () => [
  withBiz(inst(`biz|${REAL_BIZ}`, [inst('set|2', [inst('module|3', [leaf(11), leaf(12)]), inst('module|4')])])),
];
const spaceHarness = (query = {}) => harness(query, false, undefined, undefined, SPACE_BIZ);
const topoCalls = h => h.calls.filter(call => call.name === 'getHostTopoTreeByBizId').length;
const clickRow = async (h, id) => {
  const row = h.topo.visibleRows.value.find(item => item.id === id);
  assert.ok(row, id);
  h.topo.handleSelectNode(row);
  h.store.nodeId = row.id;
  await flush();
};

test('space entry backfills the default root placeholder with the authorized real root', async () => {
  const h = spaceHarness();
  await flush();
  assert.equal(h.topo.selectedNode.value.id, `biz|${SPACE_BIZ}`);
  h.respond('getHostTopoTreeByBizId', spaceSkeleton(), args => args[2] === false);
  await flush();
  assert.equal(h.topo.scopeError.value, false);
  assert.equal(h.topo.selectedNode.value.id, `biz|${REAL_BIZ}`);
  assert.equal(h.topo.selectedNode.value.bk_biz_id, SPACE_BIZ);
  assert.deepEqual(h.topo.selectedIds.value, [`biz|${REAL_BIZ}`]);
  assert.ok(
    h.pending('getHostInfoPage', ([p]) => p.bk_biz_id === SPACE_BIZ && p.bk_obj_id === 'biz' && p.bk_inst_id === REAL_BIZ)
  );
  h.respond('getHostTopoTreeByBizId', spaceFullTree(), args => args[2] !== false);
  await flush();
  assert.equal(h.topo.selectedNode.value.id, `biz|${REAL_BIZ}`);
  assert.equal(h.topo.fullTreeReady.value, true);
  assert.equal(h.store.nodeId, '');
  h.app.unmount();
});

test('late space topology does not overwrite a set/host selection made while loading', async () => {
  const h = spaceHarness();
  await flush();
  h.store.nodeId = '11';
  await flush();
  assert.equal(h.topo.selectedNode.value.id, '11');
  h.respond('getHostTopoTreeByBizId', spaceSkeleton(), args => args[2] === false);
  await flush();
  assert.equal(h.topo.selectedNode.value.id, '11');
  h.respond('getHostTopoTreeByBizId', spaceFullTree(), args => args[2] !== false);
  await flush();
  assert.equal(h.topo.selectedNode.value.bk_host_id, 11);
  h.app.unmount();

  const set = spaceHarness();
  await flush();
  set.respond('getHostTopoTreeByBizId', spaceSkeleton(), args => args[2] === false);
  await flush();
  await clickRow(set, 'set|2');
  set.respond('getHostTopoTreeByBizId', spaceFullTree(), args => args[2] !== false);
  await flush();
  assert.equal(set.topo.selectedNode.value.id, 'set|2');
  set.app.unmount();
});

test('clicked real space root keeps URL identity across tree refresh and URL reopen', async () => {
  const h = spaceHarness();
  await flush();
  h.respond('getHostTopoTreeByBizId', spaceSkeleton(), args => args[2] === false);
  await flush();
  await clickRow(h, 'set|2');
  await clickRow(h, `biz|${REAL_BIZ}`);
  assert.equal(h.store.nodeId, `biz|${REAL_BIZ}`);
  assert.equal(h.topo.scopeError.value, false);
  assert.equal(h.topo.selectedNode.value.id, `biz|${REAL_BIZ}`);
  const before = topoCalls(h);
  h.topo.handleRefresh();
  await flush();
  assert.equal(topoCalls(h), before + 2, 'refresh requests skeleton and complete topology');
  assert.deepEqual(h.pending('getHostTopoTreeByBizId', args => args[2] === false).args[0], SPACE_BIZ);
  h.respond('getHostTopoTreeByBizId', spaceSkeleton(), args => args[2] === false);
  await flush();
  assert.equal(h.topo.selectedNode.value.id, `biz|${REAL_BIZ}`);
  assert.equal(h.topo.loadError.value, false);
  h.app.unmount();

  const reopened = spaceHarness({ nodeId: `biz|${REAL_BIZ}` });
  await flush();
  assert.equal(reopened.topo.scopeError.value, false);
  assert.equal(reopened.topo.selectedNode.value, null);
  assert.equal(topoCalls(reopened), 2);
  assert.equal(reopened.calls.filter(call => call.name !== 'getHostTopoTreeByBizId').length, 0);
  reopened.respond('getHostTopoTreeByBizId', spaceSkeleton(), args => args[2] === false);
  await flush();
  assert.equal(reopened.topo.selectedNode.value.id, `biz|${REAL_BIZ}`);
  assert.equal(reopened.topo.selectedNode.value.bk_biz_id, SPACE_BIZ);
  assert.ok(reopened.pending('getHostInfoPage', ([p]) => p.bk_biz_id === SPACE_BIZ && p.bk_inst_id === REAL_BIZ));
  reopened.app.unmount();
});

test('space entry rejects unauthorized roots without widening and recovers on a valid target', async () => {
  const h = spaceHarness({ nodeId: 'biz|999' });
  await flush();
  h.respond('getHostTopoTreeByBizId', spaceSkeleton(), args => args[2] === false);
  await flush();
  assert.equal(h.topo.scopeError.value, true);
  assert.equal(h.topo.loadError.value, true);
  assert.equal(h.topo.selectedNode.value, null);
  h.respond('getHostTopoTreeByBizId', spaceFullTree(), args => args[2] !== false);
  await flush();
  assert.equal(h.topo.loadError.value, true, 'late complete topology must not revive a rejected target');
  assert.equal(h.calls.filter(call => call.name !== 'getHostTopoTreeByBizId').length, 0);
  const before = topoCalls(h);
  h.topo.handleRefresh();
  await flush();
  assert.equal(topoCalls(h), before);
  h.route.query.nodeId = 'set|2';
  await flush();
  assert.equal(h.topo.scopeError.value, false);
  assert.equal(topoCalls(h), before + 2);
  h.respond('getHostTopoTreeByBizId', spaceSkeleton(), args => args[2] === false);
  await flush();
  assert.equal(h.topo.selectedNode.value.id, 'set|2');
  assert.equal(h.topo.loadError.value, false);
  h.app.unmount();

  for (const nodeId of ['biz|-1', 'set|-2', '-11']) {
    const invalid = spaceHarness({ nodeId });
    await flush();
    assert.equal(invalid.topo.scopeError.value, true, nodeId);
    assert.equal(invalid.calls.length, 0, nodeId);
    invalid.app.unmount();
  }
  const positive = harness({ nodeId: 'biz|2' });
  await flush();
  assert.equal(positive.topo.scopeError.value, true);
  assert.equal(positive.calls.length, 0);
  positive.app.unmount();
});

test('unassociated space can use its negative root alias as the authorized root', async () => {
  const aliasTree = () => [{ ...inst(`biz|${SPACE_BIZ}`, [inst('set|2', [inst('module|3')])]), bk_biz_id: SPACE_BIZ }];
  for (const query of [{}, { nodeId: `biz|${SPACE_BIZ}` }]) {
    const h = spaceHarness(query);
    await flush();
    assert.equal(h.topo.scopeError.value, false);
    assert.equal(h.topo.selectedNode.value.id, `biz|${SPACE_BIZ}`);
    h.respond('getHostTopoTreeByBizId', aliasTree(), args => args[2] === false);
    await flush();
    assert.equal(h.topo.selectedNode.value.id, `biz|${SPACE_BIZ}`);
    assert.equal(h.topo.selectedNode.value.name, `biz|${SPACE_BIZ}`);
    h.app.unmount();
  }
});

test('positive business root and node URLs keep their selection and refresh', async () => {
  const h = harness();
  await flush();
  h.respond('getHostTopoTreeByBizId', skeleton(), args => args[2] === false);
  await flush();
  assert.equal(h.topo.selectedNode.value.id, 'biz|1');
  await clickRow(h, 'biz|1');
  assert.equal(h.topo.scopeError.value, false);
  const before = topoCalls(h);
  h.topo.handleRefresh();
  await flush();
  assert.equal(topoCalls(h), before + 2);
  h.app.unmount();
  const node = harness({ nodeId: 'module|3' });
  await flush();
  node.respond('getHostTopoTreeByBizId', skeleton(), args => args[2] === false);
  await flush();
  assert.equal(node.topo.selectedNode.value.id, 'module|3');
  node.app.unmount();
});

const scopeHarness = (query, readonly = true, workerResponse) =>
  harness({ from: '100', to: '200', ...query }, readonly, workerResponse, undefined, SPACE_BIZ, true);
const pendingHttp = (h, name, predicate = () => true) =>
  h.http.calls.find(call => !call.done && call.name === name && predicate(call.params));
const respondHttp = (h, name, result, predicate) => {
  const call = pendingHttp(h, name, predicate);
  assert.ok(call, name);
  call.done = true;
  call.resolve(result);
};
const confirmRoot = async (h, tree = spaceSkeleton()) => {
  respondHttp(h, 'getTopoTree', tree, params => !params.instance_type);
  await flush();
};
const rootQuery = instId => ({ shareTargetType: 'topo', shareBkObjId: 'biz', shareBkInstId: String(instId) });
const assertRootParams = params => {
  assert.equal(params.bk_biz_id, SPACE_BIZ);
  assert.equal(params.bk_obj_id, 'biz');
  assert.equal(params.bk_inst_id, REAL_BIZ);
  assert.equal('pending' in params, false);
};

test('root share formatter reopens readonly only after authorization and keeps request space context', async () => {
  const source = scopeHarness({}, false);
  await flush();
  await confirmRoot(source);
  const token = source.formatShare({ default_time_range: ['100', '200'], lock_search: true });
  assert.deepEqual(token.data.scope, { version: 1, target_type: 'topo', bk_obj_id: 'biz', bk_inst_id: REAL_BIZ });
  assert.equal(token.data.params.id, `biz|${REAL_BIZ}`);
  source.app.unmount();

  const urlQuery = Object.fromEntries(Object.entries(token.data.query).filter(([, value]) => value !== undefined).map(([key, value]) => [key, String(value)]));
  for (const query of [urlQuery, rootQuery(SPACE_BIZ), { ...rootQuery(REAL_BIZ), nodeId: 'module|999' }, { nodeId: `biz|${REAL_BIZ}` }, { nodeId: `biz|${SPACE_BIZ}` }]) {
    const h = scopeHarness(query);
    await flush();
    assert.equal(h.topo.scopeError.value, false);
    assert.equal(h.topo.selectedNode.value, null);
    assert.equal(h.http.calls.length, 2);
    for (const call of h.http.calls) {
      assert.equal(call.name, 'getTopoTree');
      assert.equal(call.params.bk_biz_id, SPACE_BIZ);
      assert.equal(call.params.bk_obj_id, 'biz');
      assert.equal('pending' in call.params, false);
    }
    await confirmRoot(h);
    assert.equal(h.topo.selectedNode.value.id, `biz|${REAL_BIZ}`);
    assert.equal(h.topo.selectedNode.value.bk_biz_id, SPACE_BIZ);
    assertRootParams(pendingHttp(h, 'getHostOrTopoNodeDetail').params);
    assertRootParams(pendingHttp(h, 'searchHostInfo', params => params.page === 1).params);
    assertRootParams(pendingHttp(h, 'searchHostInfo', params => !params.page).params);
    for (const call of h.http.calls.filter(call => call.name === 'searchHostMetricStats' || call.name === 'searchHostMetric')) {
      assertRootParams(call.params);
      assert.equal(call.params.start_time, 100);
      assert.equal(call.params.end_time, 200);
    }
    respondHttp(h, 'getHostOrTopoNodeDetail', [{ id: 'root-detail', type: 'text' }]);
    respondHttp(h, 'searchHostInfo', { items: [host(11)], page: 1, page_size: 100, total: 1 }, p => p.page === 1);
    for (const category of ['cpu', 'mem', 'disk'])
      respondHttp(h, 'searchHostMetricStats', { complete: true, value: 5 }, p => p.category === category);
    await flush();
    assert.equal(h.detail.detailData.value[0].id, 'root-detail');
    assert.equal(h.table.data[0].bk_host_id, 11);
    assert.equal(h.statCards.stats.cpu, 5);
    if (query.shareLink) assert.ok(h.header.timeRangeDisabledTip);
    const before = h.http.calls.filter(c => c.name === 'getTopoTree').length;
    h.topo.handleRefresh();
    await flush();
    // The in-flight service requests remain shared; the confirmed root does not return to pending.
    assert.equal(h.topo.selectedNode.value.id, `biz|${REAL_BIZ}`);
    assert.ok(h.http.calls.filter(c => c.name === 'getTopoTree').length >= before);
    h.app.unmount();
  }
});

test('readonly root charts wait for authorization and use the confirmed root target', async () => {
  for (const query of [rootQuery(REAL_BIZ), rootQuery(SPACE_BIZ)]) {
    const h = scopeHarness({ ...query, activeTab: 'metric' });
    await flush();
    assert.equal(h.chartTargets.length, 0);
    assert.equal(h.chartRequests.length, 0);
    await confirmRoot(h);
    assert.deepEqual(h.chartTargets.at(-1), [{ bk_inst_id: REAL_BIZ, bk_obj_id: 'biz' }]);
    assert.ok(h.chartRequests.length > 0);
    for (const request of h.chartRequests) {
      assert.equal(request.bizId, SPACE_BIZ);
      assert.equal(request.params.start_time, 100);
      assert.equal(request.params.end_time, 200);
      assert.deepEqual(request.params.query_configs[0].filter_dict.targets, [{ bk_inst_id: REAL_BIZ, bk_obj_id: 'biz' }]);
    }
    assertRootParams(pendingHttp(h, 'getHostOrTopoNodeDetail').params);
    h.app.unmount();
  }
});

test('readonly invalid scopes fail closed and an unauthorized root cannot revive from a late tree', async () => {
  for (const query of [
    rootQuery(-1), rootQuery(0), rootQuery('1.5'), rootQuery('9007199254740992'),
    { ...rootQuery(REAL_BIZ), shareBkInstId: [String(REAL_BIZ)] },
    { ...rootQuery(REAL_BIZ), shareBkObjId: ['biz'] },
    { shareTargetType: 'host', shareBkHostId: '-11' },
    { shareTargetType: 'topo', shareBkObjId: 'set', shareBkInstId: '-2' },
    { shareTargetType: 'topo', shareBkObjId: 'module', shareBkInstId: '-3' },
    { shareTargetType: 'invalid' },
  ]) {
    const h = scopeHarness(query);
    await flush();
    assert.equal(h.topo.scopeError.value, true, JSON.stringify(query));
    assert.equal(h.http.calls.length, 0, JSON.stringify(query));
    h.app.unmount();
  }
  const h = scopeHarness(rootQuery(999));
  await flush();
  await confirmRoot(h);
  assert.equal(h.topo.scopeError.value, true);
  assert.equal(h.topo.selectedNode.value, null);
  respondHttp(h, 'getTopoTree', spaceFullTree(), p => p.instance_type === 'host');
  await flush();
  assert.equal(h.topo.scopeError.value, true);
  assert.equal(h.http.calls.filter(call => call.name !== 'getTopoTree').length, 0);
  h.app.unmount();
});

test('readonly alias confirmation preserves token scope when a descendant is selected', async () => {
  const h = scopeHarness(rootQuery(SPACE_BIZ));
  await flush();
  await confirmRoot(h);
  const module = { ...inst('module|3'), bk_biz_id: SPACE_BIZ };
  h.topo.handleSelectNode(module);
  await flush();
  h.store.refreshGeneration++;
  await flush();
  const fullRequests = h.http.calls.filter(call =>
    (call.name === 'searchHostInfo' && !call.params.page) || call.name === 'searchHostMetric'
  );
  assert.ok(fullRequests.length);
  for (const call of fullRequests) assertRootParams(call.params);
  h.app.unmount();
});

test('readonly negative roots handle empty and unassociated topology without widening', async () => {
  for (const instId of [REAL_BIZ, SPACE_BIZ]) {
    const h = scopeHarness(rootQuery(instId));
    await flush();
    await confirmRoot(h, []);
    assert.equal(h.topo.scopeError.value, true);
    assert.equal(h.http.calls.filter(call => call.name !== 'getTopoTree').length, 0);
    h.app.unmount();
  }
  const h = scopeHarness(rootQuery(SPACE_BIZ));
  await flush();
  await confirmRoot(h, [withBiz(inst(`biz|${SPACE_BIZ}`))]);
  assert.equal(h.topo.scopeError.value, false);
  assert.equal(h.topo.selectedNode.value.id, `biz|${SPACE_BIZ}`);
  const params = pendingHttp(h, 'getHostOrTopoNodeDetail').params;
  assert.equal(params.bk_biz_id, SPACE_BIZ);
  assert.equal(params.bk_inst_id, SPACE_BIZ);
  assert.equal(params.bk_obj_id, 'biz');
  h.app.unmount();
});

test('late readonly root confirmation cannot overwrite a newer token scope', async () => {
  let release;
  const h = scopeHarness(rootQuery(SPACE_BIZ), true, value =>
    value.type === 'INIT_DONE' && value.selectedNode?.bk_obj_id === 'biz'
      ? new Promise(resolve => { release = () => resolve(value); })
      : Promise.resolve(value)
  );
  await flush();
  await confirmRoot(h);
  assert.ok(release);
  h.route.query.shareBkObjId = 'module';
  h.route.query.shareBkInstId = '3';
  await flush();
  assert.equal(h.topo.selectedNode.value.id, 'module|3');
  release();
  respondHttp(h, 'getTopoTree', spaceFullTree(), p => p.instance_type === 'host' && p.bk_obj_id === 'biz');
  await flush();
  assert.equal(h.topo.selectedNode.value.id, 'module|3');
  assert.equal(h.topo.scopeError.value, false);
  for (const call of h.http.calls.filter(call => call.name !== 'getTopoTree')) {
    assert.equal(call.params.bk_biz_id, SPACE_BIZ);
    assert.equal(call.params.bk_obj_id, 'module');
    assert.equal(call.params.bk_inst_id, 3);
  }
  h.app.unmount();
});

test('positive readonly business, module and host scopes retain their request identity', async () => {
  for (const query of [rootQuery(1), { shareTargetType: 'topo', shareBkObjId: 'module', shareBkInstId: '3' }, { shareTargetType: 'host', shareBkHostId: '11' }]) {
    const h = harness({ from: '100', to: '200', ...query }, true, undefined, undefined, 1, true);
    await flush();
    assert.equal(h.topo.scopeError.value, false);
    const params = pendingHttp(h, 'getHostOrTopoNodeDetail').params;
    assert.equal(params.bk_biz_id, 1);
    if (query.shareTargetType === 'host') assert.equal(params.bk_host_id, 11);
    else {
      assert.equal(params.bk_obj_id, query.shareBkObjId);
      assert.equal(params.bk_inst_id, Number(query.shareBkInstId));
    }
    h.app.unmount();
  }
});

test('large skeleton keeps range bounded and incremental loading does not rebuild expansion state', t => {
  const send = rawWorker('host-topo-tree');
  const tree = [
    inst('biz|1', [
      inst(
        'set|2',
        Array.from({ length: 10000 }, (_, i) => inst(`module|${i + 10}`))
      ),
    ]),
  ];
  const start = performance.now();
  send({ type: 'INIT', treeData: tree, complete: false, hideEmptyNode: true });
  send({ type: 'EXPAND_ALL', start: 0, end: 40 });
  const initMs = performance.now() - start;
  const before = performance.now();
  send({
    type: 'UPSERT_CHILDREN',
    parentId: 'module|10',
    children: Array.from({ length: 100 }, (_, i) => leaf(i + 1)),
    page: { status: 'more', total: 200 },
    anchorId: 'module|11',
  });
  const rows = send({ type: 'GET_RANGE', start: 0, end: 40 }).rows;
  assert.equal(rows.length, 40);
  assert.ok(rows.find(row => row.id === 'module|10').isExpanded);
  t.diagnostic(
    `10000-module skeleton init+expand=${initMs.toFixed(1)}ms, page upsert+range=${(performance.now() - before).toFixed(1)}ms`
  );
});

test('same HostPage instance switches business and share scopes and ignores old topology/pages', async () => {
  const h = harness({ nodeId: 'module|3' });
  await flush();
  const oldPage = h.pending('getHostInfoPage');
  const oldSkeleton = h.pending('getHostTopoTreeByBizId', args => args[2] === false);
  h.appStore.bizId = 2;
  await flush();
  assert.equal(h.topo.selectedNode.value.id, 'biz|2');
  const newPages = h.calls.filter(call => call.name === 'getHostInfoPage' && call.args[0].bk_biz_id === 2);
  assert.equal(newPages.length, 1);
  assert.equal(newPages[0].args[0].bk_inst_id, 2);
  oldSkeleton.resolve(skeleton());
  oldPage.resolve({ items: [host(11)], total: 1, page: 1, page_size: 100 });
  await flush();
  assert.equal(h.topo.selectedNode.value.id, 'biz|2');
  assert.equal(h.table.data.length, 0);
  assert.equal(h.topo.visibleRows.value.length, 0);
  h.app.unmount();

  const shared = harness({ shareTargetType: 'topo', shareBkObjId: 'module', shareBkInstId: '3' }, true);
  await flush();
  const first = shared.pending('getHostInfoPage');
  shared.route.query = { shareTargetType: 'topo', shareBkObjId: 'module', shareBkInstId: '4' };
  await flush();
  assert.equal(shared.topo.selectedNode.value.id, 'module|4');
  const second = shared.calls.filter(call => call.name === 'getHostInfoPage' && call.args[0].bk_inst_id === 4);
  assert.equal(second.length, 1);
  first.resolve({ items: [host(11)], total: 1, page: 1, page_size: 100 });
  await flush();
  assert.equal(shared.table.data.length, 0);
  const count = shared.calls.length;
  shared.route.query = { shareTargetType: 'host', shareBkHostId: 'bad' };
  await flush();
  assert.equal(shared.topo.selectedNode.value, null);
  assert.equal(shared.calls.length, count);
  shared.app.unmount();
});

test('same-route node query updates the list scope without reloading the complete topology', async () => {
  const h = harness({ nodeId: 'module|3' });
  await flush();
  h.route.query.nodeId = 'module|4';
  await flush();
  assert.equal(h.topo.selectedNode.value.id, 'module|4');
  assert.equal(h.pending('getHostInfoPage', ([p]) => p.bk_inst_id === 4).args[0].page, 1);
  assert.equal(h.calls.filter(call => call.name === 'getHostTopoTreeByBizId').length, 2);
  h.app.unmount();
});

test('actual host system/share chart waits for exact metadata, independently of topology', async () => {
  for (const readonly of [false, true]) {
    const h = harness(
      { nodeId: '11', activeTab: 'system', ...(readonly ? { shareTargetType: 'host', shareBkHostId: '11' } : {}) },
      readonly
    );
    await flush();
    assert.equal(h.chartTargets.length, 0);
    assert.deepEqual(h.pending('getHostInfoPage').args[0], { bk_biz_id: 1, bk_host_id: 11, page: 1, page_size: 1 });
    assert.equal(h.topo.selectedNode.value.metadataPending, true);
    h.respond('getHostInfoPage', { items: [{ ...host(11), bk_cloud_id: 7 }], page: 1, page_size: 1, total: 1 });
    await flush();
    assert.deepEqual(h.chartTargets.at(-1), [{ bk_host_id: 11, bk_target_ip: '127.0.0.11', bk_target_cloud_id: 7 }]);
    assert.equal(h.topo.fullTreeReady.value, false);
    assert.equal(h.restores, 1);
    h.app.unmount();
  }
});

test('actual HostProcess service requests ID before metadata, then mounts detail chart without refetching list', async () => {
  const h = harness({ nodeId: '11', activeTab: 'process', hostProcessName: 'fixture-process', from: '100', to: '200' });
  await flush();
  const processCall = h.pending('getHostProcessList');
  assert.deepEqual(processCall.args[0], { bk_biz_id: 1, bk_host_id: 11, start_time: 100, end_time: 200 });
  h.respond('getHostProcessList', [{ name: 'fixture-process', ports: [], hostIp: '127.0.0.11' }]);
  await flush();
  assert.equal(h.processTable.data.length, 1);
  assert.equal(h.chartTargets.length, 0);
  assert.equal(h.calls.filter(call => call.name === 'getHostProcessUptime').length, 0);
  h.respond('getHostInfoPage', { items: [{ ...host(11), bk_cloud_id: 7 }], page: 1, page_size: 1, total: 1 });
  await flush();
  assert.deepEqual(h.chartTargets.at(-1), [{ bk_host_id: 11, bk_target_ip: '127.0.0.11', bk_target_cloud_id: 7 }]);
  assert.equal(h.calls.filter(call => call.name === 'getHostProcessList').length, 1);
  assert.equal(h.pending('getHostProcessUptime').args[0].bk_host_id, 11);
  h.app.unmount();
});

test('actual process detail remount shares pending uptime through its service', async () => {
  const owner = {};
  const query = { nodeId: '11', activeTab: 'process', hostProcessName: 'fixture-process', from: '100', to: '200' };
  const open = async () => {
    const h = harness({ ...query }, false, undefined, owner);
    await flush();
    h.respond('getHostProcessList', [{ name: 'fixture-process', ports: [], hostIp: '127.0.0.11' }]);
    h.respond('getHostInfoPage', { items: [{ ...host(11), bk_cloud_id: 7 }], page: 1, page_size: 1, total: 1 });
    await flush();
    return h;
  };
  const first = await open();
  assert.equal(first.pending('getHostProcessUptime').args[0].bk_host_id, 11);
  assert.deepEqual(first.pending('getHostProcessUptime').args[1], { needMessage: false });
  first.app.unmount();
  const second = await open();
  assert.equal(second.calls.filter(call => call.name === 'getHostProcessUptime').length, 0);
  first.respond('getHostProcessUptime', { value: 60 });
  await flush();
  second.app.unmount();
  const third = await open();
  assert.equal(third.calls.filter(call => call.name === 'getHostProcessUptime').length, 1);
  third.respond('getHostProcessUptime', { value: 70 });
  await flush();
  third.app.unmount();
});

const findElement = (element, predicate) =>
  predicate(element) ? element : element.children?.map(child => findElement(child, predicate)).find(Boolean);

test('metadata failure shows retry, retry loads charts, and full topology may recover an empty result', async () => {
  const h = harness({ nodeId: '11', activeTab: 'system' });
  await flush();
  h.respond('getHostInfoPage', new Error('fixture'), undefined, true);
  await flush();
  assert.equal(h.topo.hostMetadataError.value, true);
  assert.equal(h.chartTargets.length, 0);
  const status = findElement(h.element, node => node.props?.role === 'status');
  assert.ok(status);
  const button = findElement(status, node => node.type === 'button');
  assert.ok(button);
  button.props.onClick();
  await flush();
  assert.equal(h.topo.hostMetadataError.value, false);
  h.respond('getHostInfoPage', { items: [host(11)], page: 1, page_size: 1, total: 1 });
  await flush();
  assert.equal(h.chartTargets.at(-1)[0].bk_host_id, 11);
  h.app.unmount();
  const empty = harness({ nodeId: '11', activeTab: 'system' });
  await flush();
  empty.respond('getHostInfoPage', { items: [], page: 1, page_size: 1, total: 0 });
  await flush();
  assert.equal(empty.topo.hostMetadataError.value, true);
  assert.equal(empty.chartTargets.length, 0);
  empty.respond('getHostTopoTreeByBizId', fullTree(), args => args[2] !== false);
  await flush();
  assert.equal(empty.chartTargets.at(-1)[0].bk_host_id, 11);
  assert.equal(
    findElement(empty.element, node => node.props?.role === 'status'),
    undefined
  );
  empty.app.unmount();
});

test('late metadata cannot overwrite a different host, business, or complete IPv6-only topology metadata', async () => {
  const h = harness({ nodeId: '11', activeTab: 'system' });
  await flush();
  const first = h.pending('getHostInfoPage');
  h.route.query.nodeId = '12';
  await flush();
  first.resolve({ items: [host(11)], page: 1, page_size: 1, total: 1 });
  await flush();
  assert.equal(h.topo.selectedNode.value.bk_host_id, 12);
  assert.equal(h.chartTargets.length, 0);
  const ipv6 = { ...leaf(12), ip: '', bk_host_innerip: '', bk_host_innerip_v6: '2001:db8::12', bk_cloud_id: 8 };
  h.respond('getHostTopoTreeByBizId', [inst('biz|1', [ipv6])], args => args[2] !== false);
  await flush();
  assert.equal(h.chartTargets.at(-1)[0].bk_host_id, 12);
  assert.equal(h.topo.selectedNode.value.bk_host_innerip_v6, '2001:db8::12');
  h.respond('getHostInfoPage', { items: [host(12)], page: 1, page_size: 1, total: 1 }, ([p]) => p.bk_host_id === 12);
  await flush();
  assert.equal(h.topo.selectedNode.value.bk_host_innerip_v6, '2001:db8::12');
  assert.equal(h.chartTargets.at(-1)[0].bk_target_cloud_id, 8);
  h.app.unmount();
  const shared = harness({ shareTargetType: 'host', shareBkHostId: '11', activeTab: 'system' }, true);
  await flush();
  const old = shared.pending('getHostInfoPage');
  shared.appStore.bizId = 2;
  await flush();
  old.resolve({ items: [host(11)], page: 1, page_size: 1, total: 1 });
  await flush();
  assert.equal(shared.topo.selectedNode.value.bk_biz_id, 2);
  assert.equal(shared.topo.selectedNode.value.metadataPending, true);
  assert.equal(shared.chartTargets.length, 0);
  assert.equal(shared.pending('getHostInfoPage', ([p]) => p.bk_biz_id === 2).args[0].bk_host_id, 11);
  shared.app.unmount();
});

for (const transition of ['business', 'share', 'unmount']) {
  test(`late Worker range cannot overwrite topology after ${transition}`, async () => {
    let hold = false;
    let release;
    const shared = transition === 'share';
    const h = harness(
      shared ? { shareTargetType: 'topo', shareBkObjId: 'module', shareBkInstId: '3' } : {},
      shared,
      result =>
        hold
          ? new Promise(resolve => {
              release = () => resolve(result);
            })
          : Promise.resolve(result)
    );
    await flush();
    h.respond('getHostTopoTreeByBizId', skeleton(), args => args[2] === false);
    await flush();
    await flush();
    hold = true;
    h.topo.handleViewportChange(0, 3000, { scrollTop: 0 });
    assert.ok(release, 'old Worker range is pending');
    if (transition === 'business') h.appStore.bizId = 2;
    else if (shared) h.route.query = { shareTargetType: 'topo', shareBkObjId: 'module', shareBkInstId: '4' };
    else h.app.unmount();
    await flush();
    const rows = h.topo.visibleRows.value;
    const total = h.topo.totalRows.value;
    if (transition !== 'unmount') assert.equal(rows.length, 0);
    release();
    await flush();
    assert.equal(h.topo.visibleRows.value, rows, 'stale response must not replace visible rows');
    assert.equal(h.topo.totalRows.value, total);
    if (transition !== 'unmount') h.app.unmount();
  });
}

for (const shared of [false, true]) {
  test(`late Worker selection cannot complete the new ${shared ? 'shared host' : 'business'} tree`, async () => {
    let release;
    const h = harness(shared ? { shareTargetType: 'host', shareBkHostId: '11' } : {}, shared, result =>
      result.type === 'SELECT_DONE'
        ? new Promise(resolve => {
            release = () => resolve(result);
          })
        : Promise.resolve(result)
    );
    await flush();
    h.respond('getHostTopoTreeByBizId', shared ? fullTree() : skeleton(), args => shared || args[2] === false);
    await flush();
    assert.ok(release, 'old tree initialization is waiting for selection');
    h.appStore.bizId = 2;
    await flush();
    assert.equal(h.topo.loading.value, true);
    assert.equal(h.topo.selectedNode.value.bk_biz_id, 2);
    release();
    await flush();
    assert.equal(h.topo.selectedNode.value.bk_biz_id, 2, 'old selected node must not overwrite the new scope');
    assert.equal(h.topo.loading.value, true, 'old initialization must not finish the new load');
    assert.equal(h.topo.visibleRows.value.length, 0);
    h.app.unmount();
  });
}

test('topology skeleton stays visible until Worker viewport rows are ready', async () => {
  const releases = [];
  const h = harness({}, false, result =>
    result.type === 'GET_RANGE_DONE'
      ? new Promise(resolve => releases.push(() => resolve(result)))
      : Promise.resolve(result)
  );
  await flush();
  assert.equal(h.topo.loading.value, true);
  h.respond('getHostTopoTreeByBizId', skeleton(), args => args[2] === false);
  await flush();
  assert.ok(releases.length);
  assert.equal(h.topo.loading.value, true);
  for (let step = 0; step < 4 && releases.length; step++) {
    releases.splice(0).forEach(release => release());
    await flush();
  }
  assert.equal(h.topo.loading.value, false);
  assert.ok(h.topo.visibleRows.value.length);
  h.app.unmount();
});

test('topology Worker viewport failure ends loading and shows an error instead of an endless skeleton', async () => {
  const h = harness({}, false, result =>
    result.type === 'GET_RANGE_DONE' ? Promise.reject(new Error('viewport failed')) : Promise.resolve(result)
  );
  await flush();
  h.respond('getHostTopoTreeByBizId', new Error('skeleton unavailable'), args => args[2] === false, true);
  h.respond('getHostTopoTreeByBizId', fullTree(), args => args.length === 2);
  await flush();
  await flush();
  assert.equal(h.topo.loading.value, false);
  assert.equal(h.topo.loadError.value, true);
  assert.equal(h.topo.fullTreeLoading.value, false);
  h.app.unmount();
});
