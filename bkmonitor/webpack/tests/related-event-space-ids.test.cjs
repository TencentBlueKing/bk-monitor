const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const ts = require('typescript');
const Vue = require('../src/trace/node_modules/vue');
const tick = () => new Promise(resolve => setImmediate(resolve));
const t = text => text;
const h = (_, props, ...children) => ({ props, children: children.flat(Infinity) });
const scripts = new Map();
function load(file, deps) {
  if (!scripts.has(file)) {
    const text = fs.readFileSync(path.resolve(__dirname, '../src', file), 'utf8');
    const js = ts.transpileModule(text, {
      fileName: file,
      compilerOptions: {
        target: ts.ScriptTarget.ES2022,
        module: ts.ModuleKind.CommonJS,
        jsx: ts.JsxEmit.React,
        jsxFactory: 'h',
        experimentalDecorators: true,
      },
    }).outputText;
    scripts.set(file, new Function('exports', 'require', 'h', 'window', js));
  }
  const result = {};
  scripts.get(file)(result, id => deps[id] ?? {}, h, { i18n: { t, tc: t } });
  return result;
}
function spaceIdCell(node) {
  if (node?.children?.[0]?.children?.[0] === '空间ID') return node.children[1].children[0];
  for (const child of node?.children || []) {
    const value = spaceIdCell(child);
    if (value !== undefined) return value;
  }
}
function fixture(version, paged) {
  const calls = [];
  const store = { bizList: [{ bk_biz_id: -8, space_id: 'old-eight' }] };
  const directory = {
    supportsSpaceDirectoryPages: () => paged,
    querySpaceDirectory: opts => new Promise((resolve, reject) => calls.push({ ...opts, resolve, reject })),
  };
  const selection = load('monitor-common/utils/space-selection.ts', { './space-directory': directory });
  const readers = load('monitor-common/utils/related-event-spaces.ts', {
    './space-directory': directory,
    './space-selection': selection,
  });
  const deps = {
    'monitor-common/utils/related-event-spaces': readers,
    dayjs: { default: { tz: () => ({ format: () => '' }) } },
    vue: Vue,
    'vue-i18n': { useI18n: () => ({ t }) },
    '@/store/modules/app': { useAppStore: () => store },
    'vue-property-decorator': {
      Component: () => component => component,
      Prop: () => () => {},
      Ref: () => () => {},
      Watch: () => () => {},
    },
    'vue-tsx-support': { Component: class {} },
  };
  if (version === 3) {
    const props = Vue.reactive({ data: [] });
    const component = load(
      'trace/pages/alarm-center/common-detail/components/panel-alarm/panel-alarm-table.tsx',
      deps
    ).default;
    const scope = Vue.effectScope();
    const state = scope.run(() => component.setup(props, { emit() {} }));
    return {
      calls,
      show: rows => {
        props.data = rows;
      },
      close: () => scope.stop(),
      cell: id =>
        state.columns.find(col => col.colKey === 'bk_biz_id').cell(null, { row: { bk_biz_id: id } }).children[0],
      expanded: id => spaceIdCell(state.getChildSlotsComponent({ bk_biz_id: id })),
    };
  }
  const Klass = load('fta-solutions/pages/event/event-detail/related-events.tsx', deps).default;
  const vm = Object.assign(new Klass(), { $store: { getters: store }, $t: t, $tc: t });
  vm.created();
  return {
    calls,
    show(rows) {
      vm.data.events = rows;
      return vm.updateSpaceIds(rows);
    },
    close() {},
    cell: id => vm.tableColumns.find(col => col.id === 'bk_biz_id').props.formatter({ bk_biz_id: id }),
    expanded: id => spaceIdCell(vm.getChildSlotsComponent({ bk_biz_id: id })),
  };
}
for (const version of [2, 3]) {
  test('Vue ' + version + ' event list and expanded details use only confirmed IDs on the visible page', async () => {
    const f = fixture(version, true);
    f.show([{ bk_biz_id: -8 }, { bk_biz_id: -9 }, { bk_biz_id: 2 }, { bk_biz_id: -8 }]);
    await tick();
    assert.equal(f.calls.length, 1);
    assert.deepEqual(f.calls[0].bkBizIds, [-8, -9]);
    f.calls[0].resolve({ items: [{ bk_biz_id: -8, space_id: 'project-eight' }], nextCursor: null, partial: true });
    await tick();
    assert.deepEqual([f.cell(-8), f.expanded(-8)], ['project-eight', 'project-eight']);
    assert.deepEqual([f.cell(-9), f.expanded(-9), f.cell(2)], [-9, -9, 2]);
    f.show([{ bk_biz_id: -10 }]);
    await tick();
    f.show([{ bk_biz_id: -11 }]);
    await tick();
    f.calls[2].resolve({ items: [{ bk_biz_id: -11, space_id: 'project-eleven' }], nextCursor: null });
    f.calls[1].resolve({ items: [{ bk_biz_id: -10, space_id: 'stale' }], nextCursor: null });
    await tick();
    assert.deepEqual([f.cell(-10), f.expanded(-11)], [-10, 'project-eleven']);
    f.close();
  });
  test('Vue ' + version + ' continues resolving legacy rows from the existing full directory', async () => {
    const f = fixture(version, false);
    f.show([{ bk_biz_id: -8 }]);
    await tick();
    assert.deepEqual(f.calls, []);
    assert.deepEqual([f.cell(-8), f.expanded(-8)], ['old-eight', 'old-eight']);
    f.close();
  });
}
