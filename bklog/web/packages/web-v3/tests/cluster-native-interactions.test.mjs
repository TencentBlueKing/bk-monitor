import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import ts from 'typescript';
import { parse, compileTemplate } from '@vue/compiler-sfc';
const slider = readFileSync(
  new URL('../src/features/clusters/current/cluster-manage/es-slider.tsx', import.meta.url),
  'utf8',
);
const table = readFileSync(
  new URL('../src/features/clusters/current/cluster-manage/index.tsx', import.meta.url),
  'utf8',
);
function initializer(source, name) {
  const ast = ts.createSourceFile('component.tsx', source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  let result;
  function visit(node) {
    if (ts.isVariableDeclaration(node) && node.name.getText(ast) === name) result = node.initializer.getText(ast);
    ts.forEachChild(node, visit);
  }
  visit(ast);
  assert.ok(result, `actual component initializer ${name} exists`);
  return result;
}
function actual(source, name, deps) {
  const code = ts.transpile(`const result = ${initializer(source, name)};`, {
    target: ts.ScriptTarget.ES2022,
    jsx: ts.JsxEmit.React,
    jsxFactory: 'h',
  });
  return new Function(...Object.keys(deps), `${code};return result;`)(...Object.values(deps));
}
const ref = (value) => ({ value });
test('invalid native Form result never reaches ES connectivity API', async () => {
  for (const result of [false, undefined, { cluster_name: [{ message: 'required' }] }]) {
    let requests = 0;
    const call = actual(slider, 'handleTestConnect', {
      validateForm: ref({ validate: async () => result }),
      ServicesInstance: {
        source: {
          connectivityDetect: () => {
            requests++;
          },
        },
      },
      connectLoading: ref(false),
      dealWithHotColdData() {},
    });
    await call();
    assert.equal(requests, 0);
  }
});
test('valid connectivity retains V2 payload, masked-password behavior and node defaults', async () => {
  const calls = [];
  const formData = ref({ setup_config: {} });
  const connectResult = ref('');
  const connectLoading = ref(false);
  const call = actual(slider, 'handleTestConnect', {
    validateForm: ref({ validate: async () => true }),
    bkBizId: ref(900001),
    basicFormData: ref({
      cluster_name: 'test',
      display_name: 'Test',
      domain_name: 'test.invalid',
      port: '9200',
      schema: 'https',
      auth_info: { username: 'user', password: '******' },
    }),
    isEdit: ref(false),
    props: {},
    connectLoading,
    connectResult,
    formData,
    hotColdOriginList: ref([]),
    dealWithHotColdData() {},
    ServicesInstance: {
      source: {
        connectivityDetect: async (...args) => calls.push(args),
        getNodeAttrs: async (...args) => {
          calls.push(args);
          return { data: [{ attr: 'hot', value: 'yes' }] };
        },
      },
    },
  });
  await call();
  assert.deepEqual(calls[0], [
    {
      data: {
        bk_biz_id: 900001,
        cluster_name: 'test',
        display_name: 'Test',
        domain_name: 'test.invalid',
        port: '9200',
        schema: 'https',
        es_auth_info: { username: 'user', password: '' },
      },
    },
    { catchIsShowMessage: false },
  ]);
  assert.deepEqual(calls[1], [calls[0][0]]);
  assert.equal(formData.value.setup_config.es_shards_default, 1);
  assert.equal(connectResult.value, 'success');
  assert.equal(connectLoading.value, false);
});
test('invalid native form prevents ES create and edit submission', async () => {
  for (const result of [false, { port: [{ message: 'required' }] }]) {
    let requests = 0;
    const call = actual(slider, 'handleConfirm', {
      checkSelectItem: () => true,
      isDoris: ref(false),
      validateForm: ref({ validate: async () => result }),
      confirmLoading: ref(false),
      ServicesInstance: {
        source: {
          create: () => {
            requests++;
          },
        },
      },
    });
    await call();
    assert.equal(requests, 0);
  }
});
test('drawer close awaits unsaved guard, respects veto and suppresses duplicate close', async () => {
  const code = ts.transpile(
    `let closePending=false; const close=${initializer(slider, 'handleCancel')}; return close;`,
    { target: ts.ScriptTarget.ES2022 },
  );
  let resolve;
  let calls = 0;
  let events = [];
  const close = new Function('handleCloseSidebar', 'emit', code)(
    () => {
      calls++;
      return new Promise((r) => {
        resolve = r;
      });
    },
    (e) => events.push(e),
  );
  const first = close();
  await close();
  assert.equal(calls, 1);
  resolve(false);
  await first;
  assert.deepEqual(events, []);
  const second = close();
  resolve(true);
  await second;
  assert.deepEqual(events, ['handleCancelSlider']);
});
test('native table retains conditional columns, status filters, data cells and permitted operations', () => {
  const edits = [];
  const deps = {
    computed: (fn) => ref(fn()),
    checkcFields: () => true,
    activeTab: ref('es'),
    CLUSTER_TYPES: { DORIS: 'doris' },
    t: (text) => text,
    sourceFilters: ref([{ text: '来源A', value: 'a' }]),
    sourceStateFilters: ref([
      { text: '正常', value: true },
      { text: '失败', value: false },
    ]),
    getStateText: (id) => `state:${id}`,
    formatFileSize: (v) => `${v}B`,
    getPercent: () => 0.5,
    TProgress: 'Progress',
    renderColumnSettings: () => null,
    authorityMapComputed: ref({ MANAGE_ES_SOURCE_AUTH: 'manage' }),
    editDataSource: (row) => edits.push(row),
    createIndexSet() {},
    deleteDataSource() {},
    h: (tag, props, ...children) => ({ tag, props, children }),
  };
  const cols = actual(table, 'tableColumns', deps).value;
  assert.equal(
    cols.filter((c) => c.colKey === 'cluster_config.cluster_id').length,
    1,
    'status and ID have unique column keys',
  );
  const row = {
    cluster_config: { cluster_id: 7, display_name: 'Cluster', domain_name: 'es.invalid' },
    is_editable: false,
    permission: { manage: false },
  };
  assert.equal(cols.find((c) => c.colKey === 'id').cell(null, { row }), 7);
  assert.equal(cols.find((c) => c.colKey === 'cluster_config.display_name').cell(null, { row }), 'Cluster');
  assert.equal(cols.find((c) => c.title === '连接状态').cell(null, { row }), 'state:7');
  assert.deepEqual(cols.find((c) => c.title === '连接状态').filter.list, [
    { label: '正常', value: 'true' },
    { label: '失败', value: 'false' },
  ]);
  const actions = cols
    .find((c) => c.colKey === 'operate')
    .cell(null, { row })
    .children.flat();
  assert.equal(actions.length, 3);
  assert.ok(actions.every((a) => a.props.disabled));
  actions[1].props.onOnClick();
  assert.deepEqual(edits, [row]);
  const doris = actual(table, 'tableColumns', { ...deps, activeTab: ref('doris') }).value;
  assert.ok(!doris.some((c) => c.title === '冷热数据'));
  assert.equal(
    doris
      .find((c) => c.colKey === 'operate')
      .cell(null, { row })
      .children.flat().length,
    1,
  );
});
test('clearing native filters clears the old query as well, false status remains filterable', () => {
  const tableFilters = ref({});
  const filterParams = ref({ source_type: 'old' });
  let data;
  const change = actual(table, 'handleNativeFilterChange', {
    tableFilters,
    filterParams,
    handleFilterChange: (value) => {
      data = value;
    },
  });
  change({ 'cluster_config.cluster_id': false });
  assert.deepEqual(data, { 'cluster_config.cluster_id': 'false' });
  assert.deepEqual(filterParams.value, {});
  change({});
  assert.deepEqual(data, {});
});
test('management router outlet is outside the native menu', () => {
  const source = readFileSync(new URL('../src/features/management/manage/index.vue', import.meta.url), 'utf8');
  const ast = compileTemplate({
    source: parse(source).descriptor.template.content,
    filename: 'manage.vue',
    id: 'test',
  }).ast;
  let outlets = 0;
  function visit(node, inMenu = false) {
    if (node.type === 1) {
      if (node.tag === 'router-view') {
        outlets++;
        assert.equal(inMenu, false);
      }
      inMenu ||= node.tag === 't-menu';
    }
    for (const child of node.children ?? []) visit(child, inMenu);
    for (const branch of node.branches ?? []) visit(branch, inMenu);
  }
  visit(ast);
  assert.ok(outlets > 0);
});
