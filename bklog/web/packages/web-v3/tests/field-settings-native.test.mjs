import { test } from 'node:test';
import assert from 'node:assert/strict';
import * as Vue from 'vue';
import { loadScriptSetup } from './helpers/load-script-setup.mjs';
import { loadTypeScript } from './helpers/load-typescript.mjs';
import { OverlayRegistry, shouldHideOnOutsideClick } from '../src/shared/global/overlay/overlay-registry.js';
const { toWorkerMessage } = loadTypeScript(new URL('../src/shared/lib/worker-message.ts', import.meta.url), {
  vue: Vue,
});
const root = new URL('../src/features/retrieval/workbench/result-comp/', import.meta.url);
const fields = [
  { field_name: 'log', field_type: 'text', query_alias: 'Message', es_doc_values: false },
  { field_name: 'level', field_type: 'keyword', es_doc_values: true },
  { field_name: 'host', field_type: 'keyword', es_doc_values: true },
  { field_name: 'virtual', field_type: '__virtual__', es_doc_values: true },
  { field_name: 'flat', field_type: 'flattened', es_doc_values: true },
];
const store = {
  state: { storage: {}, globals: { fieldTypeMap: { keyword: { color: 'red', icon: 'test-icon' } } } },
  getters: { filteredFieldList: fields },
};
const bindings = {
  useStore: () => store,
  useLocale: () => ({ $t: (value) => value }),
  getRegExp: (value) => new RegExp(value, 'i'),
  BK_LOG_STORAGE: { TEXT_ELLIPSIS_DIR: 'dir' },
  toWorkerMessage,
  overlayRegistry: new OverlayRegistry(),
  random: () => String(Math.random()),
  mapGetters: () => ({}),
};
function setup(file, props) {
  const component = loadScriptSetup(new URL(file, root), bindings);
  const scope = Vue.effectScope();
  let exposed;
  const model = scope.run(() =>
    component.setup(Vue.reactive(props), {
      expose: (value) => {
        exposed = value;
      },
    }),
  );
  return { model, scope, exposed };
}
test('field draft initializes ordered metadata, searches aliases and supports add/remove/all/clear', () => {
  const { model, scope } = setup('update/field-setting.vue', { initData: ['level', 'log'] });
  assert.deepEqual(
    model.shadowVisible.value.map((field) => field.field_name),
    ['level', 'log'],
  );
  assert.equal(model.shadowVisible.value[1].first_name, 'Message');
  model.searchKeyword.value = 'host';
  assert.deepEqual(
    model.shadowTotal.value.map((field) => field.field_name),
    ['host'],
  );
  model.addField(model.shadowTotal.value[0]);
  assert.equal(model.shadowVisible.value.length, 3);
  const previous = globalThis.Element;
  class TestElement {
    hasAttribute() {
      return true;
    }
  }
  globalThis.Element = TestElement;
  try {
    model.deleteField({ target: new TestElement() }, null, 0);
    assert.equal(model.shadowVisible.value.length, 3);
    model.deleteField({ target: null }, null, 0);
    assert.equal(model.shadowVisible.value.length, 2);
  } finally {
    if (previous === undefined) delete globalThis.Element;
    else globalThis.Element = previous;
  }
  scope.stop();
});
test('field draft add-all excludes virtual fields and clearing never mutates source metadata', () => {
  const { model, scope } = setup('update/field-setting.vue', { initData: [] });
  model.addAllField();
  assert.ok(!model.shadowVisible.value.some((field) => field.field_type === '__virtual__'));
  model.deleteAllField();
  assert.deepEqual(model.shadowVisible.value, []);
  assert.equal(fields.length, 5);
  scope.stop();
});
test('sort draft preserves order, metadata and direction; clearing uses V2 empty-string semantics', () => {
  const { model, scope } = setup('update/table-sort.vue', { initData: [['level', 'desc']], shouldRefresh: false });
  assert.deepEqual(model.shadowSort.value, [['level', 'desc']]);
  assert.ok(model.selectList.value.find((field) => field.field_name === 'level').disabled);
  assert.ok(!model.selectList.value.some((field) => ['__virtual__', 'flattened'].includes(field.field_type)));
  model.addTableItem();
  const entry = model.sortList.value[1];
  model.updateSortValue(entry.sorts, 0, 'host');
  model.updateSortValue(entry.sorts, 1, 'asc');
  assert.deepEqual(model.shadowSort.value, [
    ['level', 'desc'],
    ['host', 'asc'],
  ]);
  model.updateSortValue(entry.sorts, 1, undefined);
  assert.deepEqual(entry.sorts, ['host', '']);
  assert.equal(model.shadowSort.value.length, 1);
  model.deleteTableItem(model.sortList.value[0].key);
  assert.deepEqual(model.shadowSort.value, []);
  scope.stop();
});
for (const prefix of ['', 'update/'])
  test(`${prefix || 'classic/'}config actions clone Vue3 proxies and preserve operation payload`, async () => {
    const component = loadScriptSetup(new URL(`${prefix}fields-setting-operate.vue`, root), bindings);
    const original = Vue.reactive({
      id: 17,
      name: 'test',
      index: 2,
      display_fields: ['log'],
      sort_list: [['level', 'desc']],
    });
    const events = [];
    let focused = 0;
    await component.methods.emitOperate.call(
      {
        configItem: original,
        nameStr: 'renamed',
        $emit: (...args) => events.push(args),
        $nextTick: (fn) => fn(),
        $refs: {
          inputRef: {
            focus() {
              focused++;
            },
          },
        },
      },
      'edit',
    );
    assert.equal(events[0][0], 'operateChange');
    assert.equal(events[0][1], 'edit');
    assert.equal(events[0][2].id, 17);
    assert.equal(events[0][2].editStr, 'test');
    assert.notEqual(events[0][2], original);
    assert.deepEqual(events[0][2].display_fields, ['log']);
    assert.equal(focused, prefix ? 1 : 0);
  });
test('current field settings caches native reactive drafts without structured-clone errors', async () => {
  const component = loadScriptSetup(new URL('update/fields-setting.vue', root), bindings);
  const vm = {
    isTemplateConfig: false,
    localVisibleFields: ['log'],
    shadowVisible: Vue.reactive(['log']),
    shadowSort: Vue.reactive([['level', 'desc']]),
    initShadowFields() {},
  };
  await component.methods.initRequestConfigListShow.call(vm);
  assert.deepEqual(vm.cachedVisibleFields, ['log']);
  assert.deepEqual(vm.cachedSortFields, [['level', 'desc']]);
  assert.notEqual(vm.cachedSortFields, vm.shadowSort);
});
test('shared popovers allocate an overlay layer without requiring the removed UI library global', () => {
  const registry = new OverlayRegistry();
  const { default: Popover } = loadTypeScript(new URL('../src/shared/global/pop-instance-util.ts', import.meta.url), {
    vue: Vue,
    'lodash-es': { debounce: (fn) => fn },
    'tippy.js': () => {},
    './overlay/overlay-registry': { overlayRegistry: registry },
    './pop-instance-util.scss': {},
  });
  const pop = new Popover({ refContent: 'fixture' });
  const previous = globalThis.window;
  delete globalThis.window;
  try {
    const first = pop.getDefaultOption();
    const second = pop.getDefaultOption();
    const layers = [];
    pop.tippyInstance = {setProps: options => layers.push(options.zIndex)};
    first.onShow();
    second.onShow();
    assert.ok(layers[1] > layers[0]);
    globalThis.window = { __bk_zIndex_manager: { nextZIndex: () => 9001 } };
    pop.getDefaultOption().onShow();
    assert.equal(layers.at(-1), 9001);
  } finally {
    if (previous === undefined) delete globalThis.window;
    else globalThis.window = previous;
  }
});
test('shared popover merges retain lifecycle order, veto and reference positioning callback', () => {
  const registry = new OverlayRegistry();
  const { default: Popover } = loadTypeScript(new URL('../src/shared/global/pop-instance-util.ts', import.meta.url), {
    vue: Vue,
    'lodash-es': { debounce: (fn) => fn },
    'tippy.js': () => {},
    './overlay/overlay-registry': { overlayRegistry: registry },
    './pop-instance-util.scss': {},
  });
  const events = [];
  const rect = () => ({ width: 10, height: 20 });
  const pop = new Popover({
    refContent: 'fixture',
    onHiddenFn: () => {
      events.push('owner');
      return false;
    },
    tippyOptions: { onHide: () => events.push('custom'), getReferenceClientRect: rect, zIndex: 123 },
  });
  const merged = pop.getMergeTippyOptions();
  assert.equal(merged.onHide(), false);
  assert.deepEqual(events, ['custom', 'owner']);
  assert.equal(merged.getReferenceClientRect, rect);
  assert.deepEqual(merged.getReferenceClientRect(), { width: 10, height: 20 });
  assert.equal(merged.zIndex, 123);
});

test('save-as template validates before writes and preserves full fields and explicit/default sorts', async () => {
  store.state.indexFieldInfo = { default_sort_list: [['level', undefined]] };
  const calls = [];
  const props = { sortList: [], displayFields: ['host', 'log'], confirmHandler: async (...args) => calls.push(args) };
  const { model, scope } = setup('update/children/save-as-popover.vue', props);
  let cleared = 0;
  model.visible.value = true;
  model.formRef.value = { validate: async () => ({ editStr: [{ result: false }] }), clearValidate: () => cleared++ };
  await model.handleConfirm();
  assert.equal(calls.length, 0);
  assert.equal(model.visible.value, true);
  model.formRef.value.validate = async () => true;
  model.formModel.editStr = 'test-draft';
  await model.handleConfirm();
  assert.deepEqual(calls[0], [
    { editStr: 'test-draft', display_fields: ['host', 'log'], sort_list: [['level', 'desc']] },
    true,
    '模板保存成功，请在字段模板中查看。',
  ]);
  assert.equal(model.visible.value, false);
  assert.equal(model.formModel.editStr, '');
  assert.equal(cleared, 1);
  props.sortList = [['host', 'asc']];
  model.formModel.editStr = 'explicit';
  await model.handleConfirm();
  assert.deepEqual(calls[1][0].sort_list, [['host', 'asc']]);
  scope.stop();
  delete store.state.indexFieldInfo;
});

test('save-as failure keeps the draft open for retry; cancel clears form validation', async () => {
  const { model, scope } = setup('update/children/save-as-popover.vue', {
    sortList: [['host', 'asc']],
    displayFields: ['host'],
    confirmHandler: async () => {
      throw new Error('test failure');
    },
  });
  let cleared = 0;
  model.formRef.value = { validate: async () => true, clearValidate: () => cleared++ };
  model.visible.value = true;
  model.formModel.editStr = 'retry';
  await assert.rejects(model.handleConfirm(), /test failure/);
  assert.equal(model.visible.value, true);
  assert.equal(model.formModel.editStr, 'retry');
  model.handleCancel();
  assert.equal(model.visible.value, false);
  assert.equal(model.formModel.editStr, '');
  assert.equal(cleared, 1);
  scope.stop();
});

test('overlay retains inside-click identity when Vue removes the clicked field row before document handling', () => {
  const removedRow = { closest: () => null };
  const overlay = { closest: (selector) => (selector === '.field-overlay' ? overlay : null) };
  const event = { target: removedRow, composedPath: () => [removedRow, overlay, {}] };
  assert.equal(shouldHideOnOutsideClick(event, { rootSelector: '.field-overlay' }), false);
  assert.equal(
    shouldHideOnOutsideClick(
      { target: removedRow, composedPath: () => [removedRow] },
      { rootSelector: '.field-overlay' },
    ),
    true,
  );
  const registry = new OverlayRegistry();
  registry.register('fields', { rootSelector: '.field-overlay', hide() {} });
  assert.equal(registry.isClickInsideRecord(event, 'fields'), true);
});

test('template list keeps ordinary, union, scene and embedded request contracts', async () => {
  const source = new URL(
    '../src/features/retrieval/workbench/field-filter-comp/update/field-list.vue',
    import.meta.url,
  );
  const previous = globalThis.window;
  const previousDocument = globalThis.document;
  globalThis.document = { body: {} };
  try {
    for (const mode of ['single', 'union', 'scene', 'embedded']) {
      globalThis.window = { __IS_MONITOR_COMPONENT__: mode === 'embedded' };
      const calls = [];
      const localStore = {
        state: {
          bkBizId: 5000140,
          indexItem: { scene_active: 'test-scene' },
          unionIndexList: [16176, 16462],
          isUnionSearch: mode === 'union',
          storage: {},
        },
        getters: { isSceneMode: mode === 'scene', isUnionSearch: mode === 'union' },
      };
      const component = loadScriptSetup(source, {
        useStore: () => localStore,
        useLocale: () => ({ $t: (value) => value }),
        useRoute: () => ({ params: { indexId: '16176' }, query: { indexId: '16462' } }),
        ServicesInstance: {
          retrieve: {
            sceneListConfig: async (options) => {
              calls.push(['scene', options]);
              return { data: [] };
            },
            getFieldsListConfig: async (options) => {
              calls.push(['normal', options]);
              return { data: [] };
            },
          },
        },
      });
      const model = component.setup({}, { expose() {}, emit() {} });
      await model.getFiledConfigList();
      const expected =
        mode === 'scene'
          ? { bk_biz_id: 5000140, scene_id: 'test-scene', scope: 'default' }
          : {
              ...(mode === 'union'
                ? { index_set_ids: [16176, 16462] }
                : { index_set_id: mode === 'embedded' ? '16462' : '16176' }),
              scope: 'default',
              index_set_type: mode === 'union' ? 'union' : 'single',
            };
      assert.deepEqual(calls, [[mode === 'scene' ? 'scene' : 'normal', { data: expected }]]);
      assert.equal(model.isLoading.value, false);
    }
  } finally {
    if (previous === undefined) delete globalThis.window;
    else globalThis.window = previous;
    if (previousDocument === undefined) delete globalThis.document;
    else globalThis.document = previousDocument;
  }
});

test('native template delete confirmation remains local until explicit confirmation', () => {
  const component = loadScriptSetup(new URL('update/fields-setting-operate.vue', root), bindings);
  const operations = [];
  const vm = { deleteVisible: false, emitOperate: (type) => operations.push(type) };
  vm.handleDeleteTipPopoverHide = () => component.methods.handleDeleteTipPopoverHide.call(vm);
  component.methods.handleDeleteTipPopoverShow.call(vm);
  assert.equal(vm.deleteVisible, true);
  assert.deepEqual(operations, []);
  vm.handleDeleteTipPopoverHide();
  assert.equal(vm.deleteVisible, false);
  assert.deepEqual(operations, []);
  component.methods.handleDeleteTipPopoverShow.call(vm);
  component.methods.handleDeleteVerify.call(vm);
  assert.equal(vm.deleteVisible, false);
  assert.deepEqual(operations, ['delete']);
});

function setupAliases() {
  const original = Vue.reactive([
    { field_name: '__ext', field_type: 'object' },
    { field_name: '__ext.pod', field_type: 'keyword', query_alias: 'pod', metadata: { fixed: true } },
    { field_name: 'log', field_type: 'text', query_alias: 'message' },
    { field_name: 'virtual', field_type: '__virtual__' },
  ]);
  const calls = [];
  const events = new Map();
  const component = loadScriptSetup(
    new URL('../src/features/retrieval/workbench/field-filter-comp/update/field-alias.vue', import.meta.url),
    {
      useStore: () => ({
        getters: { rawFieldList: original },
        dispatch: async (name) => calls.push(['dispatch', name]),
      }),
      useRoute: () => ({ params: { indexId: '16176' } }),
      useLocale: () => ({ t: (value) => value }),
      useRetrieveEvent: () => ({ addEvent: (name, fn) => events.set(name, fn) }),
      RetrieveEvent: { ALIAS_CONFIG_OPEN: 'alias-open' },
      ServicesInstance: {
        retrieve: {
          updateFieldsAlias: async (options) => {
            calls.push(['save', options]);
            return { code: 0 };
          },
        },
      },
      toWorkerMessage,
      overlayRegistry: new OverlayRegistry(),
    },
  );
  const model = component.setup({}, { expose() {}, emit: (...args) => calls.push(['emit', ...args]) });
  return { model, original, calls, events };
}

test('alias drafts retain nested field metadata, expand/collapse without duplicating children and never mutate source', async () => {
  const { model, original } = setupAliases();
  await model.handleOpenSidebar();
  assert.equal(model.showSlider.value, true);
  const object = model.formData.value.find((row) => row.field_type === 'object' && row.children?.length);
  assert.equal(object.field_name, 'ext');
  assert.deepEqual(
    object.children.map((row) => row.field_name),
    ['__ext.pod'],
  );
  assert.ok(!model.formData.value.some((row) => row.field_type === '__virtual__'));
  const length = model.formData.value.length;
  model.expandObject(object, true);
  assert.equal(model.formData.value.length, length + 1);
  model.expandObject(object, false);
  assert.equal(model.formData.value.length, length);
  object.children[0].query_alias = 'draft_pod';
  assert.equal(original[1].query_alias, 'pod');
  model.handleCancel();
  assert.equal(model.showSlider.value, false);
  assert.deepEqual(model.formData.value, []);
});

test('alias validation preserves V2 naming restrictions and submission includes collapsed object children', async () => {
  const { model, calls } = setupAliases();
  await model.handleOpenSidebar();
  const log = model.formData.value.find((row) => row.field_name === 'log');
  for (const name of ['1bad', 'bad-name', 'log']) {
    log.query_alias = name;
    assert.equal(model.checkQueryAliasItem(log), false);
    assert.ok(log.aliasErr);
  }
  log.query_alias = 'message';
  assert.equal(model.checkQueryAliasItem(log), true);
  assert.equal(log.aliasErr, '');
  await model.submit();
  assert.deepEqual(calls.find((row) => row[0] === 'save')[1], {
    params: { index_set_id: '16176' },
    data: {
      alias_settings: [
        { field_name: '__ext.pod', query_alias: 'pod', path_type: 'keyword' },
        { field_name: 'log', query_alias: 'message', path_type: 'text' },
      ],
    },
  });
  assert.equal(model.showSlider.value, false);
  assert.ok(calls.some((row) => row[0] === 'dispatch' && row[1] === 'requestIndexSetFieldInfo'));
});


test('global alias-open event opens an untouched draft before the field Popup has ever opened', () => {
  const { model, original, calls, events } = setupAliases();
  assert.equal(model.showSlider.value, false);
  assert.equal(events.size, 1);
  events.get('alias-open')(false);
  assert.equal(model.showSlider.value, false);
  events.get('alias-open')(true);
  assert.equal(model.showSlider.value, true);
  assert.ok(model.formData.value.length > 0);
  model.formData.value.find(field => field.field_name === 'log').query_alias = 'local_draft';
  model.handleCancel();
  assert.equal(model.showSlider.value, false);
  assert.equal(original.find(field => field.field_name === 'log').query_alias, 'message');
  assert.equal(calls.some(([name]) => name === 'save'), false);
});
