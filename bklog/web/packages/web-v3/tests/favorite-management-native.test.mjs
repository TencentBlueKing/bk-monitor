import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import * as Vue from 'vue';
import { loadScriptSetup } from './helpers/load-script-setup.mjs';
const root = new URL('../src/features/retrieval/workbench/collect/', import.meta.url);
const source = (file) => readFileSync(new URL(file, root), 'utf8');
function favorite(id, name = 'Query', group = 2) {
  return {
    id,
    name,
    keyword: 'level:ERROR',
    group_id: group,
    group_name: group === 2 ? 'Team' : '个人收藏',
    search_fields: ['log'],
    visible_type: 'private',
    display_fields: ['log', 'level'],
    is_enable_display_fields: true,
    search_mode: 'ui',
    params: { ip_chooser: { host: ['127.0.0.1'] }, addition: [{ field: 'level', operator: '=', value: 'ERROR' }] },
    updated_by: 'tester',
    updated_at: id === 1 ? '2026-11-02 12:00:00' : '2026-11-03 12:00:00',
  };
}
function setup(file, props = {}, options = {}) {
  const calls = [],
    events = [];
  let confirm;
  const rows = [favorite(1), favorite(2, 'Another', 3)];
  const groups = [
    { id: 2, name: 'Team' },
    { id: 3, name: '个人收藏' },
  ];
  const services = Object.fromEntries(
    [
      'getGroupList',
      'getFavoriteList',
      'createGroup',
      'batchFavoriteUpdate',
      'batchFavoriteDelete',
      'deleteFavorite',
    ].map((name) => [
      name,
      async (request) => {
        calls.push({ name, request });
        return { result: true, data: name === 'getGroupList' ? groups : name === 'getFavoriteList' ? rows : { id: 9 } };
      },
    ]),
  );
  const store = { state: { spaceUid: 'bkcc__5000140' }, getters: { isSceneMode: options.scene ?? false } };
  const oldWindow = globalThis.window;
  globalThis.window = {
    __IS_MONITOR_APM__: options.apm ?? false,
    MONITOR_APM_APP_NAME: 'app',
    MONITOR_APM_SERVICE_NAME: 'service',
    addEventListener() {},
    removeEventListener() {},
  };
  const component = loadScriptSetup(new URL(file, root), {
    ServicesInstance: { favorite: services },
    useStore: () => store,
    useLocale: () => ({ $t: (text) => text }),
    useUtils: () => ({
      formatResponseListTimeZoneString: (list, extras) => list.map((row) => ({ ...row, ...extras() })),
    }),
    useDialogVisible: () => {
      const visible = Vue.ref(false);
      return {
        visible,
        setVisible: (value) => (visible.value = value),
        onValueChange: (value) => (visible.value = value),
      };
    },
    DialogPlugin: {
      confirm: (config) => {
        confirm = config;
        return {
          destroy() {
            calls.push({ name: 'destroy' });
          },
        };
      },
    },
    TDesignMessage() {},
  });
  const scope = Vue.effectScope();
  let exposed;
  const model = scope.run(() =>
    component.setup(Vue.reactive(props), {
      emit: (...args) => events.push(args),
      expose: (value) => (exposed = value),
    }),
  );
  return {
    model,
    calls,
    events,
    rows,
    groups,
    get confirm() {
      return confirm;
    },
    exposed,
    stop() {
      scope.stop();
      if (oldWindow === undefined) delete globalThis.window;
      else globalThis.window = oldWindow;
    },
  };
}
test('favorite management uses native controls, explicit columns and Vue3 model contract', () => {
  for (const file of ['favorite-manage-dialog.vue', 'batch-operation-menu.vue', 'favorite-detail.vue'])
    assert.doesNotMatch(
      source(file),
      /<\/?bk-(dialog|table|table-column|form|form-item|input|select|option|popover)\b|hideHandler|clearError|bkInfoBox/,
    );
  assert.match(source('favorite-manage-dialog.vue'), /COMPONENT_V_MODEL: false/);
  assert.match(source('favorite-manage-dialog.vue'), /@opened="\(\) => initData\(true\)"/);
  assert.match(source('favorite-manage-dialog.vue'), /onBeforeUnmount\(\(\) => window.removeEventListener/);
});
test('ordinary and scene list initialization preserve space and source type', async () => {
  for (const scene of [false, true]) {
    const c = setup('favorite-manage-dialog.vue', { modelValue: false }, { scene });
    try {
      await c.model.initData();
      assert.equal(c.model.allGroupList.value.length, 2);
      assert.equal(c.model.searchResultFavorites.value.length, 2);
      for (const { request } of c.calls) assert.deepEqual(request.query.source_type, scene ? 'scene' : 'index_set');
      assert.equal(c.calls[0].request.query.space_uid, 'bkcc__5000140');
    } finally {
      c.stop();
    }
  }
});
test('APM list requests preserve JSON scope and group creation preserves object scope', async () => {
  const c = setup('favorite-manage-dialog.vue', { modelValue: false }, { apm: true });
  try {
    await c.model.initData();
    for (const { request } of c.calls)
      assert.deepEqual(JSON.parse(request.query.scope), { app_name: 'app', service_name: 'service' });
    c.model.checkInputFormRef.value = { validate: async () => true, clearValidate() {} };
    c.model.addGroupData.value.name = 'New group';
    await c.model.handleAddGroupConfirm();
    assert.deepEqual(c.calls.find((x) => x.name === 'createGroup').request.data.scope, {
      app_name: 'app',
      service_name: 'service',
    });
  } finally {
    c.stop();
  }
});
test('group, search, column filters and time sorting retain all rows and metadata', async () => {
  const c = setup('favorite-manage-dialog.vue', { modelValue: false });
  try {
    await c.model.initData();
    c.model.handleSelectGroupChange('private');
    assert.deepEqual(
      c.model.searchResultFavorites.value.map((x) => x.id),
      [2],
    );
    c.model.handleSelectGroupChange('all');
    c.model.favoriteSearchValue.value = 'Another';
    c.model.handleFavoriteSearch();
    assert.deepEqual(
      c.model.displayFavorites.value.map((x) => x.id),
      [2],
    );
    c.model.favoriteSearchValue.value = '';
    c.model.handleFavoriteSearch();
    c.model.columnFilters.value = { group_name: ['Team'] };
    assert.deepEqual(
      c.model.displayFavorites.value.map((x) => x.id),
      [1],
    );
    c.model.columnFilters.value = { updated_by: ['missing'] };
    assert.equal(c.model.displayFavorites.value.length, 0);
    c.model.columnFilters.value = {};
    c.model.tableSort.value = { sortBy: 'updated_at', descending: true };
    assert.deepEqual(
      c.model.displayFavorites.value.map((x) => x.id),
      [2, 1],
    );
    assert.deepEqual(
      c.model.allGroupList.value.map((x) => x.id),
      [1, 2],
    );
    assert.deepEqual(
      c.model.tableColumns.value.map((x) => x.colKey),
      ['row-select', 'name', 'group_name', 'updated_by', 'updated_at', 'operation'],
    );
  } finally {
    c.stop();
  }
});
test('native validation failure never creates a group in manager or batch submenu', async () => {
  for (const file of ['favorite-manage-dialog.vue', 'batch-operation-menu.vue']) {
    const c = setup(
      file,
      file.startsWith('batch')
        ? { selectFavoriteList: [], favoriteGroupList: [], favoriteType: 'event' }
        : { modelValue: false },
    );
    try {
      const field = file.startsWith('batch') ? 'checkInputAddFormRef' : 'checkInputFormRef';
      c.model[field].value = { validate: async () => ({ name: [{ result: false }] }), clearValidate() {} };
      await c.model.handleAddGroupConfirm();
      assert.equal(c.calls.length, 0);
    } finally {
      c.stop();
    }
  }
});
test('batch move forwards every V2 update field and emits the destination', async () => {
  const row = favorite(1);
  const c = setup('batch-operation-menu.vue', {
    selectFavoriteList: [row],
    favoriteGroupList: [],
    favoriteType: 'event',
  });
  try {
    await c.model.handleBatchMoveToGroup(9);
    assert.deepEqual(c.calls[0], {
      name: 'batchFavoriteUpdate',
      request: {
        data: {
          params: [
            {
              id: 1,
              name: row.name,
              keyword: row.keyword,
              group_id: 9,
              search_fields: row.search_fields,
              visible_type: row.visible_type,
              display_fields: row.display_fields,
              is_enable_display_fields: true,
              ip_chooser: row.params.ip_chooser,
              addition: row.params.addition,
              search_mode: 'ui',
            },
          ],
        },
      },
    });
    assert.deepEqual(c.events, [['operateChange', 9]]);
  } finally {
    c.stop();
  }
});
test('batch menu cleanup closes both layers and clears only the local group draft', () => {
  const c = setup('batch-operation-menu.vue', {
    selectFavoriteList: [favorite(1)],
    favoriteGroupList: [],
    favoriteType: 'event',
  });
  try {
    c.model.outerMenuVisible.value = true;
    c.model.groupMenuVisible.value = true;
    c.model.addGroupData.value.name = 'Draft';
    c.exposed.closePopovers();
    assert.equal(c.model.outerMenuVisible.value, false);
    assert.equal(c.model.groupMenuVisible.value, false);
    assert.equal(c.model.addGroupData.value.name, '');
    assert.equal(c.calls.length, 0);
  } finally {
    c.stop();
  }
});
test('manager edits preserve query settings and update local data only after request', async () => {
  const c = setup('favorite-manage-dialog.vue', { modelValue: false });
  try {
    await c.model.initData();
    const row = c.model.searchResultFavorites.value[0];
    c.model.handleEditFavoriteName('Renamed', row);
    await new Promise((resolve) => setImmediate(resolve));
    const update = c.calls.find((x) => x.name === 'batchFavoriteUpdate').request.data.params[0];
    assert.equal(update.name, 'Renamed');
    assert.deepEqual(update.addition, row.params.addition);
    assert.deepEqual(update.display_fields, ['log', 'level']);
    assert.equal(row.editName, false);
  } finally {
    c.stop();
  }
});
test('single deletion is deferred until native confirmation and affects only selected id', async () => {
  const c = setup('favorite-manage-dialog.vue', { modelValue: false });
  try {
    await c.model.initData();
    c.model.handleDelete(c.model.searchResultFavorites.value[0]);
    assert.equal(c.calls.filter((x) => x.name === 'deleteFavorite').length, 0);
    await c.confirm.onConfirm();
    assert.deepEqual(c.calls.find((x) => x.name === 'deleteFavorite').request, { params: { favorite_id: 1 } });
    assert.deepEqual(
      c.model.allGroupList.value.map((x) => x.id),
      [2],
    );
  } finally {
    c.stop();
  }
});
test('detail group string comparison avoids a spurious update and preserves null group protocol', async () => {
  const c = setup('favorite-detail.vue', {
    value: favorite(1),
    groups: [
      { id: 2, name: 'Team' },
      { id: null, name: '未分组' },
    ],
    favoriteType: 'event',
  });
  try {
    c.model.handleEditGroup();
    await c.model.handleUpdateGroup();
    assert.equal(c.calls.length, 0);
    c.model.groupInput.value = 'null';
    await c.model.handleUpdateGroup();
    assert.equal(c.calls[0].request.data.params[0].group_id, null);
    assert.equal(c.events[0][1].group_name, '未分组');
  } finally {
    c.stop();
  }
});

test('opening batch delete closes both menu layers before showing confirmation', () => {
  const c = setup('batch-operation-menu.vue', {
    selectFavoriteList: [favorite(1)],
    favoriteGroupList: [],
    favoriteType: 'event',
  });
  try {
    c.model.outerMenuVisible.value = true;
    c.model.groupMenuVisible.value = true;
    c.model.handleShowBatchDeleteDialog();
    assert.equal(c.model.outerMenuVisible.value, false);
    assert.equal(c.model.groupMenuVisible.value, false);
    assert.equal(c.model.batchDeleteDialogVisible.value, true);
    assert.equal(c.calls.length, 0);
  } finally {
    c.stop();
  }
});

test('inline native input keeps a local draft and saves the entered name rather than the controlled old value',async()=>{
  const c=setup('favorite-manage-dialog.vue',{modelValue:false});
  try{await c.model.initData();const row=c.model.searchResultFavorites.value[0];c.model.handleEditName(row);
    assert.equal(c.model.nameDrafts.value[row.id],row.name);c.model.handleNameDraftChange(row.id,'Entered name');
    assert.equal(row.name,'Query');assert.equal(c.calls.filter(call=>call.name==='batchFavoriteUpdate').length,0);
    c.model.handleEditFavoriteName(c.model.nameDrafts.value[row.id],row);await new Promise(resolve=>setImmediate(resolve));
    assert.equal(c.calls.find(call=>call.name==='batchFavoriteUpdate').request.data.params[0].name,'Entered name');
    assert.equal(row.name,'Entered name');
    assert.match(source('favorite-manage-dialog.vue'),/:value="nameDrafts\[row.id\]"/);
    assert.match(source('favorite-manage-dialog.vue'),/@change="value => handleNameDraftChange\(row.id, value\)"/);
  }finally{c.stop()}
});
