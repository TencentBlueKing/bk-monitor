const assert = require('node:assert/strict');
const fs = require('node:fs');
const { createRequire } = require('node:module');
const path = require('node:path');
const test = require('node:test');
const { pathToFileURL } = require('node:url');
const ts = require('typescript');

const root = path.join(__dirname, '..');
const traceRequire = createRequire(path.join(root, 'src/trace/package.json'));
const vue = traceRequire('vue');
const lodash = traceRequire('lodash');
const vueuse = import(pathToFileURL(traceRequire.resolve('@vueuse/core')).href);
const constants = {
  DEFAULT_COLUMN_WIDTH: 120,
  DEFAULT_MIN_COLUMN_WIDTH: 80,
  RUM_FIELD_DEFAULT_COLUMN_WIDTH: {},
  RUM_SORTABLE_FIELD_TYPES: new Set(),
  RumFieldDisplayEnum: {},
};

function load(file, dependencies, target) {
  const module = { exports: {} };
  const code = ts.transpileModule(fs.readFileSync(path.join(root, file), 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  }).outputText;
  new Function('require', 'exports', 'module', 'window', code)(id => {
    if (!Object.hasOwn(dependencies, id)) throw new Error(`Unexpected dependency: ${id}`);
    return dependencies[id];
  }, module.exports, module, target);
  return module.exports;
}

async function harness(t, { controlled = [], save = async () => {} } = {}) {
  const shared = await vueuse;
  t.mock.timers.enable({ apis: ['setTimeout', 'Date'], now: 0 });
  const target = {
    space_list: [{ id: 1 }],
    cc_biz_id: 1,
    setTimeout: (...args) => setTimeout(...args),
    clearTimeout: timer => clearTimeout(timer),
  };
  const runtime = load('src/trace/micro-app-runtime.ts', {}, target);
  const release = runtime.prepareMicroAppRuntime(target)();
  const requests = [];
  const userConfig = load('src/trace/hooks/useUserConfig.ts', {
    vue,
    'monitor-api/modules/model': {
      listUserConfig: async () => [{ id: 42 }],
      createUserConfig: async () => { throw new Error('Existing config must be reused'); },
      partialUpdateUserConfig: (id, body, config) => {
        requests.push({ id, body, config });
        return save();
      },
    },
  }, target);
  const { useRumColumnConfig } = load('src/trace/pages/rum-explore/composables/use-rum-column-config.ts', {
    vue,
    '@vueuse/core': shared,
    lodash: lodash.runInContext({ setTimeout: target.setTimeout, clearTimeout: target.clearTimeout, Date }),
    '../constants': constants,
    '@/hooks/useUserConfig': userConfig,
  }, target);
  const scope = vue.effectScope();
  const columns = scope.run(() => useRumColumnConfig({
    cacheKey: 'test-column-preferences',
    layoutPreset: {},
    overrideDisplayFields: controlled,
    viewConfig: vue.shallowRef({
      fields: ['name', 'duration', 'status'].map(name => ({ name, can_displayed: true })),
      display_fields: ['name', 'duration'],
    }),
  }));
  // Let the real user-config hook resolve its existing configuration ID.
  for (let i = 0; i < 8; i++) await Promise.resolve();
  function unmount() {
    scope.stop();
    release();
  }
  t.after(unmount);
  return { columns, requests, unmount };
}

test('column edits retain the 300ms debounce and do not save twice after unmount', async t => {
  const h = await harness(t);
  h.columns.updateDisplayFields(['status', 'name']);
  t.mock.timers.tick(100);
  h.columns.updateColumnResizeWidth({ name: 240 });
  t.mock.timers.tick(299);
  assert.equal(h.requests.length, 0);
  t.mock.timers.tick(1);
  assert.equal(h.requests.length, 1);
  assert.deepEqual(JSON.parse(h.requests[0].body.value), {
    displayFields: ['status', 'name'], columnResizeWidth: { name: 240 }, version: '1.0.1',
  });
  h.unmount();
  t.mock.timers.tick(1000);
  assert.equal(h.requests.length, 1);
});

test('leaving within 300ms submits the latest preferences before runtime cancels timers', async t => {
  const h = await harness(t);
  h.columns.updateDisplayFields(['status', 'name']);
  h.columns.updateColumnResizeWidth({ name: 240 });
  h.columns.updateColumnResizeWidth({ status: 180 });
  t.mock.timers.tick(100);
  assert.equal(h.requests.length, 0);
  h.unmount();
  assert.equal(h.requests.length, 1);
  assert.deepEqual(h.requests[0], {
    id: 42,
    body: { value: JSON.stringify({
      displayFields: ['status', 'name'], columnResizeWidth: { name: 240, status: 180 }, version: '1.0.1',
    }) },
    config: { reject403: true },
  });
  h.unmount();
  t.mock.timers.tick(1000);
  assert.equal(h.requests.length, 1);
});

test('unmodified preferences and ignored controlled-column edits do not save on unmount', async t => {
  const h = await harness(t, { controlled: ['status'] });
  h.columns.updateDisplayFields(['name']);
  h.unmount();
  assert.equal(h.requests.length, 0);
});

test('controlled columns still persist resized widths on unmount', async t => {
  const resized = await harness(t, { controlled: ['status'] });
  resized.columns.updateDisplayFields(['status']);
  resized.columns.updateColumnResizeWidth({ status: 180 });
  resized.unmount();
  assert.equal(resized.requests.length, 1);
  assert.deepEqual(JSON.parse(resized.requests[0].body.value), {
    displayFields: [], columnResizeWidth: { status: 180 }, version: '1.0.1',
  });
});

test('a pending save can reject after release without accessing cleared sandbox exports', async t => {
  let rejectSave;
  const pending = new Promise((_, reject) => { rejectSave = reject; });
  const h = await harness(t, { save: () => pending });
  h.columns.updateColumnResizeWidth({ name: 240 });
  h.unmount();
  assert.equal(h.requests.length, 1);
  rejectSave(new Error('request failed after unmount'));
  await Promise.resolve();
  await Promise.resolve();
  assert.equal(h.requests.length, 1);
});
