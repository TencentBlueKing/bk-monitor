const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const ts = require('typescript');

const scopes = { allSpace: 'all-space', currentSpace: 'current-space', multiSpace: 'multi-space', spaceType: 'space-type' };
const t = value => value;
const row = id => ({ id, bk_biz_id: id, space_id: String(id), space_type_id: 'bkcc', space_name: String(id), type_name: '业务' });
const h = (type, props, ...children) => ({ type, props: props ?? {}, children: children.flat(Infinity) });
function loadModule(file, deps, window) {
  const source = fs.readFileSync(path.resolve(__dirname, '../src', file), 'utf8');
  const code = ts.transpileModule(source, { compilerOptions: {
    module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.React,
    jsxFactory: 'h', jsxFragmentFactory: 'fragment', experimentalDecorators: true,
  } }).outputText;
  const exports = {};
  new Function('require', 'exports', 'window', 'h', 'fragment', code)(id => deps[id] ?? {}, exports, window, h, 'fragment');
  return exports;
}
function load(file, deps, window) {
  return loadModule(file, deps, window).default;
}
function find(node, type) {
  if (node?.type === type) return node;
  return node?.children?.map(child => find(child, type)).find(Boolean);
}
function fixture() {
  const window = { i18n: { t, tc: t }, space_list_state: 'deferred' };
  const store = { bizList: [row(2)], bizId: 2 };
  const submitted = [], messages = [];
  const deps = {
    'vue-property-decorator': { Component: x => x, Prop: () => () => {}, Emit: () => () => {}, Ref: () => () => {}, Watch: () => () => {} },
    'vue-tsx-support': { Component: class {} },
    './type': { EScopes: scopes, EClusterType: {} },
    'monitor-api/modules/commons': { registerCluster: async data => { submitted.push(data); return true; } },
    'monitor-api/modules/model': { shareFavorite: async data => submitted.push(data) },
    'monitor-common/utils/space-directory': { supportsSpaceDirectoryPages: () => false },
    'monitor-common/utils/space-selection': { FormSpacePages: class {}, resolveSelectedSpaces: async (ids, rows) => {
      const records = ids.every(id => rows.some(row => row.id === id)) ? rows : await window.loadSpaceDirectory();
      return records.filter(row => ids.includes(row.id));
    } },
    vue: { reactive: x => x, defineComponent: x => x, shallowRef: value => ({ value }), computed: fn => ({ get value() { return fn(); } }), watch() {} },
    'vue-i18n': { useI18n: () => ({ t }) },
    '@store/modules/app': { useAppStore: () => store },
    '../../../../../hooks/use-favorite-type': { default: () => ({ value: 'trace' }) },
    'bkui-vue': { Button: 'button', Checkbox: Object.assign(() => {}, { Group: 'group' }), Dialog: 'dialog', Message: m => messages.push(m), Radio: Object.assign(() => {}, { Group: 'radio-group' }) },
    'monitor-common/utils/biz': { ETagsType: { BKCC: 'bkcc' }, SPACE_TYPE_MAP: {} },
  };
  return { window, store, submitted, messages, deps };
}
const clusterPath = 'monitor-pc/pages/resource-register/cluster-config.tsx';
const sharePath = 'trace/pages/trace-explore/components/favorite-box/components/group-tree/components/render-favorite/components/share-favorite.tsx';

test('opening resource registration space types renders authorized options from the shared directory', async () => {
  const { window, deps, messages } = fixture();
  const queries = [];
  window.space_list_page_supported = true;
  deps['monitor-api/modules/commons'].listSpaces = async params => {
    queries.push(params);
    return { items: params.type === 'bkcc' ? [row(2)] : [], next_cursor: null };
  };
  deps['monitor-common/utils'] = { random: () => 'fixture' };
  deps['monitor-common/utils/space-directory'] = loadModule('monitor-common/utils/space-directory.ts', deps, window);
  deps['../../common/constant'] = { SPACE_TYPE_MAP: { bkcc: { name: '业务' } } };
  deps['./type'].EClusterType = { ES: 'elasticsearch' };
  deps['../type'] = { EScopes: scopes, EsSpaceScopes: [] };
  const More = load('monitor-pc/pages/resource-register/cluster-config/cluster-more-config.tsx', deps, window);
  deps['./cluster-config/cluster-more-config'] = { default: More };
  const Cluster = load(clusterPath, deps, window);
  const cluster = Object.assign(new Cluster(), {
    selectedType: 'elasticsearch', rowConfig: { operationType: 'add' }, $t: t, $tc: t, $bkMessage: m => messages.push(m),
  });
  const moreProps = () => find(cluster.render(), More).props;
  const more = Object.assign(new More(), {
    selectedType: 'elasticsearch', $tc: t, spaceTypes: [],
    $emit(event, open) {
      assert.equal(event, 'openSpaceTypes');
      return moreProps().onOpenSpaceTypes.call(cluster, open);
    },
  });
  more.localFormData.elasticsearch.scope = scopes.spaceType;
  const menu = () => find(more.render(), 'bk-select');
  await menu().props.onToggle(false);
  assert.equal(queries.length, 0);
  await menu().props.onToggle(true);
  assert.deepEqual(messages, []);
  assert.deepEqual(queries.map(q => q.type).sort(), ['bcs', 'bkcc', 'bkci', 'bksaas', 'default']);
  assert.ok(queries.every(q => q.mode === 'page' && q.page_size === 1));
  more.spaceTypes = moreProps().spaceTypes;
  assert.deepEqual(menu().children.map(option => [option.props.id, option.props.name]), [['bkcc', '业务']]);
});

test('resource submit resolves every selected space and never posts a partial scope', async () => {
  const { window, store, submitted, deps } = fixture();
  const component = load(clusterPath, deps, window).prototype;
  const ctx = Object.assign(Object.create(component), {
    $store: { getters: store }, $t: t, $bkMessage() {}, validate: () => true, emitShowChange() {}, getInfoParams: () => ({}),
    formData: { label: [], moreConfig: { elasticsearch: { scope: scopes.multiSpace, space: [2, -4] } } },
  });
  for (const getSpaces of [async () => { throw new Error(); }, async () => [row(2)]]) {
    window.loadSpaceDirectory = getSpaces;
    await ctx.handleSubmit();
    assert.equal(submitted.length, 0);
    assert.equal(ctx.submitButtonLoading, false);
  }
  window.loadSpaceDirectory = async () => [row(-4), row(2)];
  await ctx.handleSubmit();
  assert.deepEqual(submitted[0].default_settings.elasticsearch.spaces, [
    { space_id: '2', space_type: 'bkcc' }, { space_id: '-4', space_type: 'bkcc' },
  ]);
  delete window.loadSpaceDirectory;
  assert.deepEqual(await ctx.getSpaceParams([], scopes.currentSpace), [{ space_id: '2', space_type: 'bkcc' }]);
  assert.deepEqual(await ctx.getSpaceParams(['bkci'], scopes.spaceType), [{ space_type: 'bkci' }]);
  assert.deepEqual(await ctx.getSpaceParams([], scopes.allSpace), []);
});

test('Trace favorite all waits for the authorized directory, handles failure and works on legacy full data', async () => {
  const { window, store, submitted, messages, deps } = fixture();
  const render = load(sharePath, deps, window).setup({ isShow: true, data: {} }, { emit() {} });
  const all = () => find(render(), deps['bkui-vue'].Checkbox).props;
  const submit = () => find(render().props['v-slots'].footer(), 'button').props;
  window.loadSpaceDirectory = async () => { throw new Error(); };
  await all().onChange(true);
  assert.equal(messages.length, 1);
  let resolve;
  window.loadSpaceDirectory = () => new Promise(done => { resolve = done; });
  const selecting = all().onChange(true);
  assert.equal(submit().disabled, true);
  resolve([row(2), row(9)]);
  await selecting;
  await submit().onClick();
  assert.deepEqual(submitted.at(-1).share_bk_biz_ids, [2, 9]);
  const old = load(sharePath, deps, Object.assign(window, { space_list_state: 'full' })).setup({ isShow: true, data: {} }, { emit() {} });
  store.bizList = [row(2), row(-4)];
  await find(old(), deps['bkui-vue'].Checkbox).props.onChange(true);
  await find(old().props['v-slots'].footer(), 'button').props.onClick();
  assert.deepEqual(submitted.at(-1).share_bk_biz_ids, [2, -4]);
});

test('manually checking all confirmed rows of a partial Trace result leaves the all-spaces checkbox clear', () => {
  const { window, deps } = fixture();
  deps['monitor-common/utils/space-directory'].supportsSpaceDirectoryPages = () => true;
  let pages;
  deps['monitor-common/utils/space-selection'].FormSpacePages = class {
    constructor() { pages = this; this.failed = true; this.items = [row(7)]; }
  };
  const render = load(sharePath, deps, window).setup({ isShow: true, data: {} }, { emit() {} });
  const selected = find(render(), 'group').props['v-model'];
  selected.push(7);
  const all = () => find(render(), deps['bkui-vue'].Checkbox).props.modelValue;
  assert.equal(all(), false);
  pages.failed = false;
  assert.equal(all(), true);
});
