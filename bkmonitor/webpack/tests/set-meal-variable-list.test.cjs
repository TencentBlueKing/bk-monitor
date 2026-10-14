const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const { escape } = require('lodash');
const ts = require('typescript');

const filename = path.join(
  __dirname,
  '../src/fta-solutions/pages/setting/set-meal/set-meal-add/meal-desc/variable-list/variable-list.tsx'
);
const referenceValues = {
  A: { value: 4, state: 'SUCCESS' },
  B: { value: 6, state: 'SUCCESS' },
  C: { value: 9, state: 'SUCCESS' },
  RESULT: { value: 10, state: 'SUCCESS' },
};

function component(options = {}) {
  const metadata = { ALARM_VAR: [{ name: 'alarm.ref_values', example: referenceValues }] };
  const module = { exports: {} };
  const code = ts.transpileModule(fs.readFileSync(filename, 'utf8'), {
    fileName: filename,
    reportDiagnostics: true,
    compilerOptions: {
      module: ts.ModuleKind.CommonJS,
      target: ts.ScriptTarget.ES2020,
      experimentalDecorators: true,
      jsx: ts.JsxEmit.React,
      jsxFactory: 'h',
    },
  });
  assert.deepEqual(code.diagnostics, []);
  const load = id => {
    if (id.endsWith('/store/modules/set-meal-add')) {
      return { __esModule: true, default: { getVariableTable: metadata, getVariablePanels: [] } };
    }
    if (id.endsWith('.scss')) return {};
    return require(id);
  };
  new Function('require', 'module', 'exports', 'window', code.outputText)(
    load,
    module,
    module.exports,
    { i18n: { t: value => value } }
  );
  const vm = new module.exports.default({ methods: { $tc: value => value, ...options } });
  return { vm, metadata };
}

test('meal variable popover renders A/B/C/RESULT object examples as JSON', () => {
  const { vm } = component();
  const content = vm.getContent(referenceValues);
  assert.ok(content.includes(escape(JSON.stringify(referenceValues))));
  assert.ok(!content.includes('[object Object]'));
  vm.$destroy();
});

test('meal variable popover preserves scalar text and formats array examples', () => {
  const { vm } = component();
  for (const value of ['text', '', 0, false, null, undefined, [1, 2]]) {
    const expected = Array.isArray(value) ? JSON.stringify(value) : String(value);
    assert.ok(vm.getContent(value).includes(`变量示例：${escape(expected)}</div>`));
  }
  vm.$destroy();
});

test('HTML inside a structured example is rendered as text rather than markup', () => {
  const { vm } = component();
  const payload = '<img src=x onerror=alert(1)>&"\'';
  const content = vm.getContent({ A: { value: payload, state: 'SUCCESS' } });
  assert.ok(content.includes('&lt;img'));
  assert.ok(content.includes('&amp;'));
  assert.ok(!content.includes('<img'));
  vm.$destroy();
});

test('HTML inside existing string examples is escaped', () => {
  const { vm } = component();
  const payload = '<script>alert(1)</script>';
  assert.ok(vm.getContent(payload).includes(escape(payload)));
  assert.ok(!vm.getContent(payload).includes('<script>'));
  vm.$destroy();
});

test('actual row hover passes a formatted example to the popover', () => {
  let popoverOptions;
  let shown = false;
  const { vm, metadata } = component({
    $bkPopover: (_target, options) => {
      popoverOptions = options;
      return { show: () => { shown = true; }, destroy: () => {} };
    },
  });
  const before = JSON.stringify(metadata);
  vm.handleRowEnter(0, { target: {} }, metadata.ALARM_VAR[0]);
  assert.ok(shown);
  assert.ok(popoverOptions.content.includes(escape(JSON.stringify(referenceValues))));
  assert.equal(JSON.stringify(metadata), before);
  assert.equal(vm.variableTable, metadata);
  vm.handleRowLeave();
  vm.$destroy();
});
