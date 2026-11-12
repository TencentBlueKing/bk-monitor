import { nativeStateFixture } from './helpers/native-state-fixture.mjs';
import { test } from 'node:test';
import assert from 'node:assert/strict';
import ts from 'typescript';
import { readFileSync } from 'node:fs';
import { loadTypeScript } from './helpers/load-typescript.mjs';
const root = new URL('../src/features/retrieval/workbench/field-filter-comp/', import.meta.url);
const { BK_LOG_STORAGE } = loadTypeScript(new URL('../src/app/state/store.type.ts', import.meta.url));
const { default: objectFieldTreeMeta } = loadTypeScript(new URL('object-field-tree-meta.ts', root));
class ComponentBase {}
const decorators = {
  Component: (value) => value,
  Prop: () => () => {},
  Ref: () => () => {},
  Watch: () => () => {},
  Emit: () => () => {},
  Vue: ComponentBase,
};
const store = {
  state: {
    globals: { fieldTypeMap: {} },
    storage: { [BK_LOG_STORAGE.SHOW_FIELD_ALIAS]: false },
    retrieve: { flatIndexSetList: [] },
    indexItem: {},
  },
  getters: {
    isSceneMode: false,
    isUnionSearch: false,
    unionIndexList: [16176, 16462],
    unionIndexItemList: [],
    retrieveParams: {},
    requestAddition: [],
  },
};
const common = {
  '@/app/state/domains/application-store': { useApplicationStore: () => nativeStateFixture(store) },
  '@/app/state/domains/retrieve-store': {useRetrieveStore:()=>({...store.state.retrieve,$state:store.state.retrieve})},
  '@/app/state/domains/globals-store': {useGlobalsStore:()=>({$state:store.state.globals})},
  'vue-property-decorator': decorators,
  'vue-tsx-support': { Component: ComponentBase },
  'tdesign-vue-next': {Popup: {name:'NativePopupFixture'}, Tooltip:{name:'Tooltip'}, Drawer:{name:'Drawer'}},
  './agg-chart': {},
  './field-analysis': {},
  '@/shared/lib/util': { blobDownload() {} },
  'lodash-es': { debounce: (fn) => fn, escape: (value) => value },
  '@/platform/http/index': {},
  '../../../../app/state/store.type.ts': { BK_LOG_STORAGE },
  './object-field-tree-meta': objectFieldTreeMeta,
  './field-item.scss': {},
};
const compiler = { jsx: ts.JsxEmit.ReactJSX, jsxImportSource: 'vue', experimentalDecorators: true };
const { default: FieldItem } = loadTypeScript(new URL('field-item.tsx', root), common, compiler);
function field() {
  const vm = new FieldItem();
  Object.assign(vm, {
    $store: store,
    $route: { params: { indexId: '16176' }, query: { indexId: '16462' } },
    fieldItem: { field_name: '__ext.labels.app', field_type: 'keyword', query_alias: 'appAlias', es_doc_values: true },
    retrieveParams: { keyword: '*', addition: [], start_time: 'start', end_time: 'end' },
    statisticalFieldData: {},
    isFrontStatistics: false,
    isFieldObject: false,
    type: 'visible',
  });
  return vm;
}

test('field statistics preserve ordinary, union, scene and embedded payloads and never use the alias as aggregation key', () => {
  const previous = globalThis.window;
  try {
    for (const mode of ['single', 'union', 'scene', 'embedded']) {
      globalThis.window = { __IS_MONITOR_COMPONENT__: mode === 'embedded' };
      store.getters.isSceneMode = mode === 'scene';
      store.getters.isUnionSearch = mode === 'union';
      const vm = field();
      const request = vm.queryParams;
      assert.equal(request.agg_field, '__ext.labels.app');
      assert.equal(request.field_type, 'keyword');
      assert.deepEqual(request.addition, []);
      assert.equal(request.isFrontStatisticsL, false);
      if (mode === 'scene') assert.equal('index_set_ids' in request, false);
      else
        assert.deepEqual(
          request.index_set_ids,
          mode === 'union' ? [16176, 16462] : [mode === 'embedded' ? '16462' : '16176'],
        );
      assert.equal('agg_field' in vm.retrieveParams, false);
    }
  } finally {
    store.getters.isSceneMode = false;
    store.getters.isUnionSearch = false;
    if (previous === undefined) delete globalThis.window;
    else globalThis.window = previous;
  }
});

test('nested field labels use V2 dot splitting while preserving aliases and raw aggregation keys', () => {
  const vm = field();
  vm.isFieldObject = true;
  assert.equal(vm.computedFieldName, 'app');
  store.state.storage[BK_LOG_STORAGE.SHOW_FIELD_ALIAS] = true;
  assert.equal(vm.computedFieldName, 'appAlias');
  assert.equal(vm.agg_field, '__ext.labels.app');
  store.state.storage[BK_LOG_STORAGE.SHOW_FIELD_ALIAS] = false;
});

test('native analysis popup retains V2 availability rules and explicit title/icon click handling', () => {
  const vm = field();
  let stopped = 0;
  vm.handleClickAnalysisItem({ stopPropagation: () => stopped++ });
  assert.equal(stopped, 1);
  assert.equal(vm.analysisActive, true);
  vm.handleAnalysisVisibleChange(false, { trigger: 'trigger-element-click' });
  assert.equal(vm.analysisActive, true);
  vm.handleAnalysisVisibleChange(false, { trigger: 'document' });
  assert.equal(vm.analysisActive, false);
  vm.isFrontStatistics = true;
  vm.handleClickAnalysisItem();
  assert.equal(vm.analysisActive, false);
  vm.isFrontStatistics = false;
  vm.fieldItem.field_type = 'text';
  vm.handleClickAnalysisItem();
  assert.equal(vm.analysisActive, false);
});

test('native popup owns positioning and safely closes after its reference is released', () => {
  const vm = field();vm.$t = value => value;
  const popup = () => vm.render().children[0];
  assert.equal(popup().type.name, 'NativePopupFixture');
  assert.equal(popup().props.attach, 'body');assert.equal(popup().props.placement,'right');
  assert.equal(popup().props.visible,false);assert.equal(popup().props['v-slots'].content(),null);
  vm.handleClickAnalysisItem();assert.equal(popup().props.visible,true);
  vm.analysisPopupRef=undefined;
  assert.doesNotThrow(()=>vm.handleAnalysisVisibleChange(false,{trigger:'document'}));
  assert.equal(popup().props.visible,false);assert.equal(popup().props['v-slots'].content(),null);
  assert.doesNotThrow(()=>vm.instanceDestroy());
});

test('field display toggle closes analysis and preserves the original type and field payload', () => {
  const vm = field();
  const payloads = [];
  vm.analysisActive = true;
  vm.emitToggleItem = (value) => payloads.push(value);
  vm.handleShowOrHiddenItem();
  assert.equal(vm.analysisActive, false);
  assert.deepEqual(payloads, [{ type: 'visible', fieldItem: vm.fieldItem }]);
});

const NativeInputFixture = { name: 'NativeInputFixture' };
const emittedQueryEvents = [];
function aggregateClass(requests) {
  return loadTypeScript(
    new URL('agg-chart.tsx', root),
    {
      ...common,
      'tdesign-vue-next': { Input: NativeInputFixture, Tooltip: { name: 'NativeTooltipFixture' } },
      '@/shared/utils/typed-record': { asDictionary: (value) => value },
      '@/app/skeleton/item-skeleton': {},
      '@/app/state/url-resolver': {
        RetrieveUrlResolver: class {
          constructor(params) {
            this.params = params;
          }
          resolveParamsToUrl() {
            return { keyword: this.params.keyword, addition: JSON.stringify(this.params.addition) };
          }
        },
      },
      '@/features/retrieval/retrieve-helper': {
        __esModule: true,
        default: { fire: (event) => emittedQueryEvents.push(event) },
        RetrieveEvent: { TREND_GRAPH_SEARCH: 'trend', SEARCH_VALUE_CHANGE: 'input' },
      },
      dompurify: { sanitize: (value) => value },
      '@/app/state/index': store,
      './agg-chart.scss': {},
      '@/platform/services': {
        ServicesInstance: {
          retrieve: {
            fieldFetchTopList: async (options) => {
              requests.push(['normal', options]);
              return {
                code: 0,
                data: {
                  distinct_count: 2,
                  values: [
                    ['ERROR', 4],
                    ['WARN', 2],
                  ],
                  field_count: 6,
                  total_count: 8,
                },
              };
            },
            getSceneFieldFetchTopList: async (options) => {
              requests.push(['scene', options]);
              return {
                code: 0,
                data: {
                  distinct_count: 2,
                  values: [
                    ['ERROR', 4],
                    ['WARN', 2],
                  ],
                  field_count: 6,
                  total_count: 8,
                },
              };
            },
          },
        },
      },
    },
    compiler,
  ).default;
}
function withAggregate(callback) {
  const previous = globalThis.window;
  globalThis.window = {
    mainComponent: { $route: { params: { indexId: '16176' }, query: { indexId: '16462' } }, $t: (value) => value },
  };
  const requests = [];
  const Aggregate = aggregateClass(requests);
  const vm = new Aggregate();
  Object.assign(vm, {
    fieldName: 'level',
    fieldType: 'keyword',
    retrieveParams: { start_time: 'start', end_time: 'end', addition: [] },
    isFrontStatistics: false,
    statisticalFieldData: {},
    limit: 5,
  });
  vm.emitDistinctCount = () => {};
  return Promise.resolve()
    .then(() => callback(vm, requests))
    .finally(() => {
      store.getters.isSceneMode = false;
      store.getters.isUnionSearch = false;
      if (previous === undefined) delete globalThis.window;
      else globalThis.window = previous;
    });
}

test('aggregate front statistics retain metadata exclusion, marks, top five and search clearing', () =>
  withAggregate((vm) => {
    vm.isFrontStatistics = true;
    vm.statisticalFieldData = {
      __validCount: 10,
      __totalCount: 20,
      '<mark>ERROR</mark>': 7,
      WARN: 3,
      INFO: 2,
      DEBUG: 1,
      TRACE: 1,
      OTHER: 1,
    };
    assert.equal(vm.topFiveList.length, 5);
    assert.deepEqual(vm.topFiveList[0], ['ERROR', 7]);
    vm.searchKeyword = 'WARN';
    assert.deepEqual(vm.filterList, [['WARN', 3]]);
    vm.searchKeyword = '';
    assert.equal(vm.filterList.length, 5);
    vm.showAllList = true;
    assert.equal(vm.filterList.length, 6);
    assert.equal(vm.showValidCount, 10);
    assert.equal(vm.showTotalCount, 20);
  }));

test('aggregate backend requests preserve ordinary, union, scene and embedded contexts', () =>
  withAggregate(async (vm, requests) => {
    for (const mode of ['single', 'union', 'scene', 'embedded']) {
      requests.length = 0;
      store.getters.isSceneMode = mode === 'scene';
      store.getters.isUnionSearch = mode === 'union';
      globalThis.window.__IS_MONITOR_COMPONENT__ = mode === 'embedded';
      store.getters.retrieveParams = {
        keyword: 'current',
        addition: [{ field: 'level', operator: '=', value: ['ERROR'] }],
      };
      store.getters.requestAddition = store.getters.retrieveParams.addition;
      await vm.queryFieldFetchTopList(20);
      assert.equal(requests.length, 1);
      assert.equal(requests[0][0], mode === 'scene' ? 'scene' : 'normal');
      const data = requests[0][1].data;
      assert.equal(data.agg_field, 'level');
      assert.equal(data.limit, 20);
      assert.equal(data.start_time, 'start');
      assert.equal(data.end_time, 'end');
      assert.deepEqual(data.addition, store.getters.requestAddition);
      if (mode === 'scene') assert.equal('index_set_ids' in data, false);
      else
        assert.deepEqual(
          data.index_set_ids,
          mode === 'union' ? [16176, 16462] : [mode === 'embedded' ? '16462' : '16176'],
        );
      assert.equal(vm.listLoading, false);
      assert.deepEqual(vm.fieldValueData.values, [
        ['ERROR', 4],
        ['WARN', 2],
      ]);
    }
  }));

test('aggregate native input renders search/clear/suffix icon and normalizes cleared values', () =>
  withAggregate((vm) => {
    vm.$t = (value) => value;
    vm.showSearchKeyword = true;
    vm.searchKeyword = 'WARN';
    vm.listLoading = true;
    const tree = vm.render();
    const input = tree.children[0].children[0];
    assert.equal(input.type, NativeInputFixture);
    assert.equal(input.props.value, 'WARN');
    assert.equal(input.props.clearable, true);
    assert.equal(input.props.suffixIcon().props.class, 'bklog-icon bklog-search');
    input.props.onChange('ERROR');
    assert.equal(vm.searchKeyword, 'ERROR');
    input.props.onChange(undefined);
    assert.equal(vm.searchKeyword, '');
  }));

test('field statistics business JSX contains no legacy library controls', () => {
  const legacy = [];
  for (const name of ['field-item.tsx', 'field-analysis.tsx', 'agg-chart.tsx']) {
    const ast = ts.createSourceFile(name, readFileSync(new URL(name, root), 'utf8'), ts.ScriptTarget.Latest, true);
    function visit(node) {
      if (
        (ts.isJsxOpeningElement(node) || ts.isJsxSelfClosingElement(node)) &&
        node.tagName.getText(ast).startsWith('bk-')
      )
        legacy.push(`${name}: ${node.tagName.getText(ast)}`);
      ts.forEachChild(node, visit);
    }
    visit(ast);
  }
  assert.deepEqual(legacy, []);
});

test('unmasked statistics drawer keeps inside/removed-row clicks and closes on outside mousedown', () => {
  const vm = field();
  const drawer = {};
  vm.ifShowMore = true;
  vm.statsDrawerContentRef = {
    closest: (selector) => {
      assert.equal(selector, '.agg-field-item-sideslider');
      return drawer;
    },
  };
  vm.handleDrawerOutside({ composedPath: () => [{}, drawer] });
  assert.equal(vm.ifShowMore, true);
  vm.handleDrawerOutside({ composedPath: () => [{}] });
  assert.equal(vm.ifShowMore, false);
});

test('statistics drawer outside listener is detached on hide and component teardown', () => {
  const previous = globalThis.document;
  const events = [];
  globalThis.document = {
    addEventListener: (...args) => events.push(['add', ...args]),
    removeEventListener: (...args) => events.push(['remove', ...args]),
  };
  try {
    const vm = field();
    vm.handleDrawerVisibilityChange(true);
    assert.equal(events.filter((row) => row[0] === 'add').length, 1);
    assert.equal(events[1][1], 'mousedown');
    assert.equal(events[1][3], true);
    vm.handleDrawerVisibilityChange(false);
    vm.beforeDestroy();
    assert.equal(events.filter((row) => row[0] === 'remove').length, 3);
    assert.equal(events.at(-1)[2], vm.handleDrawerOutside);
  } finally {
    if (previous === undefined) delete globalThis.document;
    else globalThis.document = previous;
  }
});

for (const [operation, expected] of [
  ['is', '='],
  ['is not', '!='],
])
  test(`aggregate query uses the live Vue host router and preserves URL context: ${operation}`, { timeout: 1000 }, () =>
    withAggregate(async (vm) => {
      const calls = [];
      const previousDispatch = store.dispatch;
      emittedQueryEvents.length = 0;
      store.dispatch = async (name, payload) => {
        calls.push(['dispatch', name, payload]);
        store.getters.retrieveParams = { keyword: '', addition: [payload] };
      };
      try {
        // Vue Class field initializers run against a collection instance. Only the
        // live host has router injections; a captured arrow ignores this receiver.
        const host = Object.create(vm);
        host.$route = { query: { spaceUid: 'bkcc__5000140', bizId: '5000140', f_11: '20680' } };
        host.$router = {
          replace: async (options) => {
            calls.push(['route', options]);
          },
        };
        let finished;
        const emitted = new Promise((resolve) => {
          finished = resolve;
        });
        host.emitAddCondition = (...args) => {
          calls.push(['emit', ...args]);
          finished();
        };
        vm.addCondition.call(host, operation, 0, 'iterationIndex');
        await emitted;
        assert.deepEqual(calls[0], [
          'dispatch',
          'setQueryCondition',
          { field: 'iterationIndex', operator: expected, value: [0] },
        ]);
        assert.deepEqual(calls[1][1].query, {
          spaceUid: 'bkcc__5000140',
          bizId: '5000140',
          f_11: '20680',
          keyword: '',
          addition: JSON.stringify([calls[0][2]]),
        });
        assert.deepEqual(emittedQueryEvents, ['trend', 'input']);
        assert.deepEqual(calls[2], ['emit', operation, 0, 'iterationIndex']);
      } finally {
        if (previousDispatch === undefined) delete store.dispatch;
        else store.dispatch = previousDispatch;
      }
    }),
  );
