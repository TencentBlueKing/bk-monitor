const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const ts = require('typescript');
const vue = require('../src/trace/node_modules/vue');
const { renderToString } = require('../src/trace/node_modules/vue/server-renderer');

const root = path.join(__dirname, '../src/trace/pages/main/llm-observation');
const modules = new Map();

// 执行实际展示组件及工具函数；样式在浏览器验证，测试不依赖整站构建。
function loadSource(file) {
  if (modules.has(file)) return modules.get(file);
  const code = ts.transpileModule(fs.readFileSync(file, 'utf8'), {
    compilerOptions: {
      module: ts.ModuleKind.CommonJS,
      target: ts.ScriptTarget.ES2020,
      jsx: ts.JsxEmit.React,
      jsxFactory: 'h',
    },
  }).outputText;
  const module = { exports: {} };
  const load = id => {
    if (id === 'vue') return vue;
    if (/\.(css|scss)$/.test(id)) return {};
    if (id === 'vue-json-pretty') return require('../src/trace/node_modules/vue-json-pretty');
    if (id.startsWith('.')) return loadSource(`${path.resolve(path.dirname(file), id)}.ts`);
    return require(id);
  };
  new Function('require', 'module', 'exports', 'h', code)(load, module, module.exports, vue.h);
  modules.set(file, module.exports);
  return module.exports;
}

const { beautifyJsonValue, formatJsonDisplay } = loadSource(`${root}/utils/helpers.ts`);
const JsonView = loadSource(`${root}/components/json-view.tsx`).default;

test('unwraps nested tool-result JSON while preserving help text and scalar string types', () => {
  const help = '=== help ===\r\n\tpath   str   [required]\n\nExample: "hello"\nargs: {"a":1}';
  const prefix = "[use_mcp_tool for 'example'] Result:";
  const envelope = `${prefix}\n${JSON.stringify({ output: JSON.stringify({ id: '123', help }) })}`;
  const result = formatJsonDisplay([{ type: 'text', text: envelope }]);
  assert.ok(result.includes(prefix));
  assert.ok(result.includes(help));
  assert.ok(result.includes('"id": "123"'));
  assert.ok(!result.includes('\\r\\n'));
});

test('preserves ordinary text, literal escapes, and invalid or trailing JSON', () => {
  for (const value of [
    'empty JSON {}',
    'args: {"a":1}',
    'Docs\nargs: {"a":1}',
    '[tool] Result: {"a":1} trailing',
    '[tool] Result: {broken}',
    String.raw`C:\new\test`,
    String.raw`\n\t\w+`,
  ]) {
    assert.equal(formatJsonDisplay(value), value);
  }
  const value = { id: '123', bool: 'false', nil: 'null', code: '00123' };
  const original = JSON.stringify(value);
  assert.deepEqual(beautifyJsonValue(value), value);
  assert.equal(JSON.stringify(value), original);
});

test('keeps existing repair support and renders null, false, zero and empty structures', () => {
  assert.deepEqual(beautifyJsonValue('{"text":"one\ntwo",}'), { text: 'one\ntwo' });
  assert.deepEqual(beautifyJsonValue(JSON.stringify(JSON.stringify({ value: [1, 2] }))), { value: [1, 2] });
  for (const value of [null, false, 0, [], {}]) assert.equal(formatJsonDisplay(value), JSON.stringify(value));
});

test('renders multiline leaves as safe text with the actual JSON tree component', async () => {
  const content = '<script>alert(1)</script>\n\tpath   str';
  const html = await renderToString(vue.createSSRApp(JsonView, { data: { output: content } }));
  assert.ok(html.includes('llm-json-view-text'));
  assert.ok(html.includes('\n\tpath   str'));
  assert.ok(html.includes('&lt;script&gt;'));
  assert.ok(!html.includes('<script>'));
});
