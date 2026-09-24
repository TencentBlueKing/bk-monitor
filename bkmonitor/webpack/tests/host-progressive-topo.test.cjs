const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');
const ts = require('typescript');
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
function treeClient(rangeResponse = value => Promise.resolve(value)) {
  const send = rawWorker('host-topo-tree');
  return {
    init: (treeData, hideEmptyNode, searchValue, selectedId, complete = true, preserve = false, anchorId = '') =>
      Promise.resolve(
        send({
          type: preserve ? 'REPLACE' : 'INIT',
          treeData,
          hideEmptyNode,
          searchValue,
          selectedId,
          complete,
          anchorId,
        })
      ),
    select: id => Promise.resolve(send({ type: 'SELECT', id })),
    getRange: (start, end) => rangeResponse(send({ type: 'GET_RANGE', start, end })),
    toggle: (id, expanded, start, end) => Promise.resolve(send({ type: 'TOGGLE', id, expanded, start, end })),
    setFilter: (hideEmptyNode, searchValue, start, end) =>
      Promise.resolve(send({ type: 'SET_FILTER', hideEmptyNode, searchValue, start, end })),
    upsertChildren: (parentId, children, page, anchorId = '') =>
      Promise.resolve(send({ type: 'UPSERT_CHILDREN', parentId, children, page, anchorId })),
    expandAll: (start, end) => Promise.resolve(send({ type: 'EXPAND_ALL', start, end })),
    collapseAll: (start, end) => Promise.resolve(send({ type: 'COLLAPSE_ALL', start, end })),
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

function harness(query = {}, readonly = false, rangeResponse) {
  global.window = { cc_biz_id: 1, timezone: 'UTC', i18n: { t: value => value } };
  global.ResizeObserver = class {
    observe() {}
    disconnect() {}
  };
  const route = vue.reactive({ query, params: {}, fullPath: '/' });
  const appStore = vue.reactive({ bizId: 1 });
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
  const services = Object.fromEntries(
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
  let topo,
    processTable,
    table,
    restores = 0;
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
    load: async () => {},
    settingShow: vue.shallowRef(false),
    loadError: vue.shallowRef(false),
    loading: vue.shallowRef(false),
    rows: vue.shallowRef([]),
    orderData: vue.shallowRef([]),
  });
  const cache = new Map();
  const own =
    /(?:host\.tsx|host-content-tabs\.tsx|host-list\.tsx|host-topo-tree\.tsx|host-process\.tsx|host-metric\.tsx|process-detail\.tsx|use-process-list\.ts|process-service\.ts|use-metric-aggregation\.ts|constants\/process\.ts|utils\/process\.ts|variables\/resolve\.ts|use-host-topo-tree\.ts|use-host-url-params\.ts|use-host-list\.ts|use-host-list-data\.ts|host-list-core\.ts|share-scope\.ts|topo-tree\.ts|constants\/enum\.ts|constants\/constants\.ts)$/;
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
      if (id.endsWith('/use-host-topo-tree-worker')) return { useHostTopoTreeWorker: () => treeClient(rangeResponse) };
      if (id.endsWith('/use-host-list-worker')) return { useHostListWorker: () => listWorker };
      if (id.endsWith('/host-service')) return services;
      if (id === 'monitor-api/modules/scene_view') return services;
      if (id.endsWith('/process-table')) return { default: ProcessTable };
      if (id.endsWith('/use-metric-groups')) return { useMetricGroups: metricGroups };
      if (id.endsWith('/use-process-metric')) return { useProcessMetric: metricGroups };
      if (id.endsWith('/dashbords')) {
        const variables = load(`${root}/components/dashbords/variables/resolve.ts`);
        return {
          ...variables,
          DashboardPanel: vue.defineComponent({
            setup:
              (_, { attrs }) =>
              () => {
                chartTargets.push(
                  variables.resolveVariables({ targets: ['$current_target', '$compare_targets'] }, attrs.scopedVars)
                    .targets
                );
                return null;
              },
          }),
        };
      }
      if (id === 'lodash') return { cloneDeep: structuredClone };
      if (id === 'dayjs') return require('dayjs');
      if (id.endsWith('/template-srv')) return { getTemplateSrv: () => ({ replace: value => value }) };
      if (id === 'monitor-ui/chart-plugins/typings')
        return {
          PanelModel: class {
            constructor(value) {
              Object.assign(this, value);
            }
          },
        };
      if (id.endsWith('/use-host-detail'))
        return { useHostDetail: () => ({ detailData: vue.shallowRef([]), loading: vue.shallowRef(false) }) };
      if (id.endsWith('/host-list-table')) return { default: Table };
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
          commonPageSizeGet: () => 100,
          tryURLDecodeParse: (value, fallback) => {
            try {
              return JSON.parse(decodeURIComponent(value));
            } catch {
              return fallback;
            }
          },
        };
      if (id === 'monitor-common/utils/utils') return {};
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
  h.app.unmount();
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
  assert.deepEqual(processCall.args[0], { bk_host_id: 11, start_time: 100, end_time: 200 });
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
