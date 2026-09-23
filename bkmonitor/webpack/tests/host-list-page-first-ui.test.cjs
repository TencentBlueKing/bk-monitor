const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const ts = require('typescript');
const vue = require('../src/trace/node_modules/vue');

const root = path.join(__dirname, '../src/trace/pages/host/components/host-list');
const component = name => ({ name });
const Button = component('Button');
const Checkbox = component('Checkbox');
const Pagination = component('Pagination');
const Input = component('Input');
const Dropdown = Object.assign(component('Dropdown'), {
  DropdownItem: component('DropdownItem'),
  DropdownMenu: component('DropdownMenu'),
});
const PrimaryTable = component('PrimaryTable');
const RetrievalFilter = component('RetrievalFilter');
const AcrossPageSelection = component('AcrossPageSelection');
const SelectType = { UN_SELECTED: 0, SELECTED: 1, HALF_SELECTED: 2, ALL_SELECTED: 3, HALF_ALL_SELECTED: 4 };
const cards = ['alarm', 'cpu', 'mem', 'disk'].map(key => ({ key, name: key }));
const columns = [
  { id: 'id', type: 'checkbox', name: 'id' },
  { id: 'bk_host_innerip', type: 'ip', name: 'IP', sortable: true },
  { id: 'cpu_usage', type: 'metric', name: 'CPU', sortable: true },
];

// 执行实际组件 setup/render 与事件；只隔离外部 UI 库、服务和浏览器生命周期。
function loadComponent(name, overrides = {}) {
  const source = fs.readFileSync(path.join(root, `${name}.tsx`), 'utf8');
  const code = ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.CommonJS,
      target: ts.ScriptTarget.ES2020,
      jsx: ts.JsxEmit.React,
      jsxFactory: 'h',
    },
  }).outputText;
  const module = { exports: {} };
  const load = id => {
    if (id in overrides) return overrides[id];
    if (/\.(scss|png)$/.test(id)) return {};
    if (id === 'vue') {
      return { ...vue, onMounted() {}, onBeforeUnmount() {}, useTemplateRef: () => vue.shallowRef(null) };
    }
    if (id === 'vue-i18n') return { useI18n: () => ({ t: value => value, locale: vue.shallowRef('zhCN') }) };
    if (id === 'bkui-vue') return { Button, Checkbox, Pagination, Input, Dropdown, Alert: component('Alert') };
    if (id === '@blueking/tdesign-ui') return { PrimaryTable };
    if (id === '@vueuse/core') return { useResizeObserver() {} };
    if (id === 'monitor-common/utils/alarm-center-router') return { openAlarmCenter() {} };
    if (id === 'tippy.js') return () => ({ show() {}, hide() {}, destroy() {} });
    if (id.endsWith('/use-table-popover')) return { useTableEllipsis: () => ({ initListeners() {} }) };
    if (id.endsWith('/use-popover')) return { usePopover: () => ({}) };
    if (id.endsWith('/across-page-selection')) return { default: AcrossPageSelection, SelectType };
    if (id.endsWith('/retrieval-filter/retrieval-filter')) return { default: RetrievalFilter };
    if (id.endsWith('/retrieval-filter/typing')) return { EMode: { ui: 'ui', queryString: 'queryString' } };
    if (id.endsWith('/use-host-list-filter')) {
      return { useHostListFilter: () => ({ refreshKey: vue.shallowRef(0), tagValueDisplayFormatter: value => value }) };
    }
    if (id.endsWith('/constants/host-list')) {
      return {
        HOST_QUICK_CARD_LIST: cards,
        HOST_LIST_COLUMNS: columns,
        HOST_LIST_PAGE_SIZE_LIST: [10, 20, 50, 100],
        HOST_METRIC_HEADER_ICON_MAP: {},
        HOST_STATUS_MAP: {},
      };
    }
    if (id.startsWith('.') || id.startsWith('@/')) return { default: component(id.split('/').at(-1)) };
    throw new Error(`Unexpected import: ${id}`);
  };
  new Function('require', 'module', 'exports', 'h', code)(load, module, module.exports, vue.h);
  return module.exports.default;
}

function setup(Component, input = {}) {
  const defaults = Object.fromEntries(
    Object.entries(Component.props).map(([key, value]) => [
      key,
      typeof value.default === 'function' ? value.default() : value.default,
    ])
  );
  const props = vue.shallowReactive({ ...defaults, ...input });
  const events = [];
  const render = Component.setup(props, { emit: (...args) => events.push(args) });
  return { props, events, render };
}

function nodes(node) {
  if (!node || typeof node !== 'object') return [];
  if (Array.isArray(node)) return node.flatMap(nodes);
  const children = Array.isArray(node.children)
    ? node.children
    : node.children && typeof node.children === 'object'
      ? Object.values(node.children)
          .filter(value => typeof value === 'function')
          .flatMap(value => value())
      : [];
  return [node, ...children.flatMap(nodes)];
}

const find = (node, type) => nodes(node).find(node => node.type === type);
const byClass = (node, className) => nodes(node).find(node => node.props?.class?.includes(className));

test('cards expose independent pending, zero and failed states without enabling filters', () => {
  const states = {
    alarm: { loading: true, error: false },
    cpu: { loading: false, error: false },
    mem: { loading: true, error: false },
    disk: { loading: false, error: true },
  };
  const view = setup(loadComponent('host-stat-cards'), {
    fullDataReady: false,
    stats: { alarm: 9, cpu: 0, mem: 7, disk: 8 },
    states,
    activeKey: 'cpu',
  });
  const [alarm, cpu, mem, disk] = view.render().children;
  assert.equal(byClass(alarm, 'host-stat-cards__num').children, '--');
  assert.equal(byClass(cpu, 'host-stat-cards__num').children, '0');
  assert.ok(byClass(mem, 'host-stat-cards__loading'));
  assert.equal(byClass(disk, 'host-stat-cards__num').children, '--');
  assert.ok(!cpu.props.class.includes('is-active'));
  for (const card of [alarm, cpu, mem, disk]) {
    assert.equal(find(card, 'button').props.disabled, true);
    find(card, 'button').props.onClick();
  }
  assert.deepEqual(view.events, []);
  const retry = find(disk, Button);
  retry.props.onClick();
  assert.deepEqual(view.events, [['retry', 'disk']]);
  view.props.fullDataReady = true;
  view.props.states = Object.fromEntries(cards.map(({ key }) => [key, { loading: false, error: false }]));
  retry.props.onClick();
  assert.equal(view.events.length, 1, 'late temporary retry cannot run after full-data handoff');
  assert.equal(find(view.render().children[0], 'button').props.disabled, false);
  assert.equal(byClass(view.render().children[0], 'host-stat-cards__num').children, '9');
  find(view.render().children[1], 'button').props.onClick();
  assert.deepEqual(view.events.at(-1), ['cardClick', 'cpu']);
});

test('toolbar blocks new global conditions while preserving copy of selected rows', () => {
  const view = setup(loadComponent('host-list-toolbar'), { disabled: true, keyword: 'saved', hasSelection: true });
  const input = find(view.render(), Input);
  assert.equal(input.props.disabled, true);
  assert.equal(input.props.modelValue, 'saved');
  input.props.onInput('new');
  input.props.onClear();
  input.props.onEnter();
  byClass(view.render(), 'host-list-toolbar__filter-btn').props.onClick();
  assert.deepEqual(view.events, []);
  assert.equal(find(view.render(), Dropdown).props.disabled, false);
  find(view.render(), Dropdown.DropdownItem).props.onClick();
  assert.deepEqual(view.events, [['copyIp', 'bk_host_innerip']]);
  view.props.disabled = false;
  find(view.render(), Input).props.onInput('new');
  assert.deepEqual(view.events.at(-1), ['keywordChange', 'new']);
});

test('paused filter shows saved values and unmounts editable retrieval UI until ready', () => {
  const where = [{ key: 'cpu', method: 'gte', value: [80] }];
  const view = setup(loadComponent('host-list-filter'), {
    disabled: true,
    filterMode: 'ui',
    where,
    fields: [{ name: 'cpu', alias: 'CPU', methods: [{ value: 'gte', alias: '>=' }] }],
    getValueFn: async () => ({ list: [], count: 0 }),
  });
  assert.equal(find(view.render(), Input).props.modelValue, 'CPU >= 80');
  assert.equal(find(view.render(), Input).props.disabled, true);
  assert.equal(find(view.render(), RetrievalFilter), undefined);
  assert.equal(view.props.where, where);
  view.props.disabled = false;
  const filter = find(view.render(), RetrievalFilter);
  filter.props.onWhereChange([]);
  assert.deepEqual(view.events, [['whereChange', []]]);
  view.props.disabled = true;
  filter.props.onWhereChange([]);
  filter.props.onSearch();
  assert.equal(view.events.length, 1, 'previous editable callbacks are blocked during a refresh');
});

test('page mode keeps pagination, page selection and drilldown but suppresses global sort and pin', () => {
  const row = { id: '1', rowId: '1', bk_host_innerip: '127.0.0.1' };
  const view = setup(loadComponent('host-list-table'), {
    data: [row],
    visibleColumns: columns.map(column => column.id),
    selectedRowKeys: new Set(['1']),
    sort: '-cpu_usage',
    markValue: { 1: 1 },
    total: 100,
  });
  let table = find(view.render(), PrimaryTable);
  assert.deepEqual(table.props.sort, []);
  assert.ok(table.props.columns.every(column => column.sorter === false));
  table.props.onSortChange([{ sortBy: 'cpu_usage', descending: true }]);
  assert.deepEqual(view.events, []);
  const checkbox = table.props.columns[0].title();
  assert.equal(checkbox.type, Checkbox);
  assert.equal(checkbox.props.modelValue, true);
  checkbox.props.onChange(true);
  assert.deepEqual(view.events.at(-1), ['headerSelect', SelectType.SELECTED]);
  const ip = table.props.columns[1].cell(null, { row });
  assert.equal(find(ip, 'svg'), undefined);
  byClass(ip, 'host-table-ip ').props.onClick();
  assert.deepEqual(view.events.at(-1), ['selectIpCell', row]);
  for (const state of [{ loading: true }, { loading: false, loadError: true }]) {
    Object.assign(view.props, state);
    const rendered = view.render();
    assert.equal(find(rendered, PrimaryTable).props.style.display, 'none');
    const pagination = find(rendered, Pagination);
    assert.equal(pagination.props.count, 100);
    pagination.props.onChange(3);
    pagination.props.onLimitChange(20);
    assert.deepEqual(view.events.slice(-2), [
      ['pageChange', 3],
      ['pageSizeChange', 20],
    ]);
  }
  view.props.fullDataReady = true;
  view.props.loadError = false;
  table = find(view.render(), PrimaryTable);
  assert.equal(table.props.columns[0].title().type, AcrossPageSelection);
  assert.equal(table.props.columns[1].sorter, true);
  assert.deepEqual(table.props.sort, [{ sortBy: 'cpu_usage', descending: true }]);
  assert.ok(find(table.props.columns[1].cell(null, { row }), 'svg'));
  table.props.onSortChange([{ sortBy: 'cpu_usage', descending: false }]);
  assert.deepEqual(view.events.at(-1), ['sortChange', 'cpu_usage']);
});

test('page loading and errors leave card data visible, preserve saved state and wire narrow retries', () => {
  const ctx = Object.fromEntries(
    Object.entries({
      selectedRowKeys: new Set(),
      fullDataReady: false,
      fullLoading: false,
      fullLoadError: true,
      loading: true,
      loadError: false,
      keyword: 'saved',
      where: [],
      queryString: '',
      activeCategory: 'cpu',
      sortInfo: '-cpu_usage',
      stickyValue: { 1: 1 },
      filterExpanded: true,
      categoryStats: { alarm: 0, cpu: 0, mem: 2, disk: 3 },
      categoryStates: {},
      filterMode: 'ui',
      filterOptionsMap: {},
      fieldsWidthConfig: {},
      pagedRows: [],
      rawRowCount: 100,
      total: 100,
      metricLoadError: false,
      metricLoading: true,
      page: 2,
      pageSize: 50,
      selectType: SelectType.UN_SELECTED,
      visibleColumns: [],
    }).map(([key, value]) => [key, vue.shallowRef(value)])
  );
  const retries = [];
  ctx.retryFullData = () => retries.push('full');
  ctx.loadPageData = () => retries.push('page');
  ctx.loadMetricData = () => retries.push('metric');
  ctx.retryCategory = key => retries.push(key);
  const HostStatCards = component('HostStatCards');
  const HostListTable = component('HostListTable');
  const view = setup(
    loadComponent('host-list', {
      pinia: { storeToRefs: value => value },
      'trace/store/modules/host': { useHostStore: () => ctx },
      '../../composables/use-host-list': { useHostList: () => ctx },
      './host-stat-cards': { default: HostStatCards },
      './host-list-table': { default: HostListTable },
    })
  );
  for (const loading of [true, false]) {
    ctx.loading.value = loading;
    ctx.loadError.value = !loading;
    const rendered = view.render();
    assert.equal(find(rendered, HostStatCards).props.stats.cpu, 0);
    assert.equal(byClass(rendered, 'host-list-content').props.style, undefined);
    const table = find(rendered, HostListTable);
    assert.deepEqual(table.props.markValue, {});
    assert.equal(table.props.sort, '');
    assert.equal(table.props.page, 2);
  }
  const rendered = view.render();
  find(rendered, HostListTable).props.onRetryPage();
  find(rendered, HostListTable).props.onRetryMetric();
  find(rendered, HostStatCards).props.onRetry('disk');
  find(rendered, Button).props.onClick();
  assert.deepEqual(retries, ['page', 'metric', 'disk', 'full']);
  assert.equal(ctx.keyword.value, 'saved');
  assert.equal(ctx.activeCategory.value, 'cpu');
  ctx.total.value = 0;
  assert.equal(find(view.render(), HostListTable).props.emptyType, 'empty');
  ctx.fullDataReady.value = true;
  assert.equal(find(view.render(), HostListTable).props.emptyType, 'search-empty');
  assert.equal(find(view.render(), HostListTable).props.sort, '-cpu_usage');
  assert.deepEqual(find(view.render(), HostListTable).props.markValue, { 1: 1 });
});
