import { test } from 'node:test';
import assert from 'node:assert/strict';
import { loadScriptSetup } from './helpers/load-script-setup.mjs';
import { loadTypeScript } from './helpers/load-typescript.mjs';
const root = new URL('../src/features/retrieval/workbench/result-comp/', import.meta.url);
const bindings = {
  mapGetters: () => ({}),
  mapState: () => ({}),
  MILLISECONDS_PER_DAY: 86400000,
  DOWNLOAD_RECENT_DAYS: 90,
};
const history = loadScriptSetup(new URL('export-history.vue', root), bindings);
const download = loadScriptSetup(new URL('export-log.vue', root), bindings);

test('native export table retains every V2 column and conditional index IDs', () => {
  const vm = { $t: (value) => value, isSearchAll: false, getTableWidth: { export_status: '230', operate: '150' } };
  assert.deepEqual(
    history.computed.historyColumns.call(vm).map((col) => col.colKey),
    ['id', 'request', 'status', 'filename', 'filesize', 'creator', 'createdAt', 'operations'],
  );
  vm.isSearchAll = true;
  assert.deepEqual(
    history.computed.historyColumns.call(vm).map((col) => col.colKey),
    ['id', 'indexSetId', 'request', 'status', 'filename', 'filesize', 'creator', 'createdAt', 'operations'],
  );
});

test('native export pagination makes one request and keeps V2 reset-on-size behavior', () => {
  let fetched = 0;
  const vm = {
    pagination: { current: 3, limit: 10, count: 50 },
    fetchHistoryList() {
      fetched++;
    },
  };
  vm.handleLimitChange = (size) => history.methods.handleLimitChange.call(vm, size);
  vm.handlePageChange = (page) => history.methods.handlePageChange.call(vm, page);
  history.methods.handleNativePageChange.call(vm, { current: 1, pageSize: 20 });
  assert.deepEqual(vm.pagination, { current: 1, limit: 20, count: 50 });
  assert.equal(fetched, 1);
  history.methods.handleNativePageChange.call(vm, { current: 2, pageSize: 20 });
  assert.equal(vm.pagination.current, 2);
  assert.equal(fetched, 2);
  history.methods.handleNativePageChange.call(vm, { current: 2, pageSize: 20 });
  assert.equal(fetched, 2);
});

test('native date presets preserve Date ranges and commit once for presets/keyboard, confirm remains explicit', () => {
  let fetched = 0;
  const vm = history.data.call({ $t: (value) => value });
  vm.handleShortcutChange = (shortcut) => history.methods.handleShortcutChange.call(vm, shortcut);
  vm.handlePickSuccess = () => fetched++;
  const presets = history.computed.nativeDatePresets.call(vm);
  const values = Object.values(presets);
  const range = values[0]();
  assert.equal(vm.shortcutSelectedIndex, 0);
  assert.ok(range.every((value) => value instanceof Date));
  history.methods.handleNativeDateChange.call(vm, range, { trigger: 'preset' });
  assert.equal(fetched, 1);
  history.methods.handleNativeDateChange.call(vm, range, { trigger: 'confirm' });
  assert.equal(fetched, 1);
  history.methods.handlePickSuccess.call({
    fetchHistoryList: (reset) => {
      assert.equal(reset, true);
      fetched++;
    },
  });
  assert.equal(fetched, 2);
  history.methods.handleNativeDateChange.call(vm, range, { trigger: 'enter' });
  assert.equal(fetched, 3);
});

test('download submit retains loading guard and quick/full/legacy branches', () => {
  for (const type of ['quick', 'all', 'legacy']) {
    const calls = [];
    const vm = {
      exportLoading: true,
      downloadType: type,
      isShowExportDialog: true,
      quickDownload: () => calls.push('quick'),
      downloadAsync: () => calls.push('all'),
      openDownloadUrl: () => calls.push('legacy'),
    };
    download.methods.handleClickSubmit.call(vm);
    assert.deepEqual(calls, []);
    vm.exportLoading = false;
    download.methods.handleClickSubmit.call(vm);
    assert.deepEqual(calls, [type]);
    assert.equal(vm.isShowExportDialog, type === 'all');
  }
});

function taskModule(dialogs, messages) {
  return loadTypeScript(new URL('download/exportTask.ts', root), {
    'tdesign-vue-next': {
      DialogPlugin: {
        confirm: (options) => {
          const dialog = {
            options,
            destroyed: false,
            destroy() {
              this.destroyed = true;
            },
          };
          dialogs.push(dialog);
          return dialog;
        },
      },
      MessagePlugin: (...args) => messages.push(args),
    },
    '@/platform/services': { ServicesInstance: {} },
    'lodash-es': { cloneDeep: (value) => structuredClone(value) },
  });
}

test('sort preflight native confirmation cancels without creating a task or mutating caller state', async () => {
  const dialogs = [],
    messages = [],
    calls = [];
  const { submitExportWithSortConfirmation } = taskModule(dialogs, messages);
  const config = { data: { sort_list: [['level', 'asc']] } };
  const operation = async (request) => {
    calls.push(structuredClone(request));
    return { result: true, data: { requires_sort_confirmation: true, sort_list: [['dtEventTimeStamp', 'desc']] } };
  };
  const pending = submitExportWithSortConfirmation({ $t: (value) => value }, operation, config);
  await Promise.resolve();
  assert.equal(dialogs.length, 1);
  assert.equal(dialogs[0].options.closeOnOverlayClick, false);
  dialogs[0].options.onClose();
  assert.equal(await pending, null);
  assert.equal(calls.length, 1);
  assert.equal(dialogs[0].destroyed, true);
  assert.deepEqual(config, { data: { sort_list: [['level', 'asc']] } });
});

test('sort preflight confirms adjusted snapshot once and rejects a second changing sort', async () => {
  const dialogs = [],
    messages = [],
    calls = [];
  const { submitExportWithSortConfirmation } = taskModule(dialogs, messages);
  const config = { data: { sort_list: [['level', 'asc']] } };
  const operation = async (request) => {
    calls.push(structuredClone(request));
    return { result: true, data: { requires_sort_confirmation: true, sort_list: [['dtEventTimeStamp', 'desc']] } };
  };
  const pending = submitExportWithSortConfirmation({ $t: (value) => value }, operation, config);
  await Promise.resolve();
  dialogs[0].options.onConfirm();
  assert.equal(await pending, null);
  assert.equal(calls.length, 2);
  assert.deepEqual(calls[1].data.sort_list, [['dtEventTimeStamp', 'desc']]);
  assert.deepEqual(config.data.sort_list, [['level', 'asc']]);
  assert.equal(dialogs.length, 1);
  assert.equal(messages[0][0], 'error');
});

test('shortcut label display restores editable dates on focus and clears selected shortcut after manual confirmation', () => {
  const vm = history.data.call({ $t: (value) => value });
  const props = history.computed.historyDateInputProps.call(vm);
  assert.equal(props.inputProps[0].value, vm.dateShortcuts[3].text);
  assert.equal(props.inputProps[1].value, '');
  vm.historyDateFocused = true;
  assert.deepEqual(history.computed.historyDateInputProps.call(vm), {});
  vm.handlePickSuccess = () => {};
  history.methods.handleNativeDateChange.call(vm, [new Date(1), new Date(2)], { trigger: 'confirm' });
  assert.equal(vm.shortcutSelectedIndex, -1);
  vm.historyDateFocused = false;
  assert.deepEqual(history.computed.historyDateInputProps.call(vm), {});
});
