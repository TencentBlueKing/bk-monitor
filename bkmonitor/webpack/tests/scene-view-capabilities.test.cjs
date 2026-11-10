const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const ts = require('typescript');

const file = path.resolve(__dirname, '../src/monitor-api/modules/scene_view.js');
const calls = [];
const moduleObject = { exports: {} };
const code = ts.transpileModule(fs.readFileSync(file, 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText;
new Function('require', 'module', 'exports', code)(id => {
  assert.equal(id, '../base');
  return { request: (method, url) => (...args) => { calls.push({ method, url, args }); return Promise.resolve(); } };
}, moduleObject, moduleObject.exports);

test('Kubernetes scene views declare native Pod query support while preserving request options', async () => {
  const params = { scene_id: 'kubernetes', type: 'detail', id: 'pod' };
  const options = { cancelToken: { id: 'fixture' }, needMessage: false };
  await moduleObject.exports.getSceneView(params, options);
  assert.deepEqual(calls.at(-1), {
    method: 'GET', url: 'rest/v2/scene_view/get_scene_view/',
    args: [{ ...params, supports_pod_memory_promql: true }, options],
  });
  assert.equal('supports_pod_memory_promql' in params, false);

  const other = { scene_id: 'host', type: 'detail', id: 'host' };
  await moduleObject.exports.getSceneView(other, options);
  assert.strictEqual(calls.at(-1).args[0], other);
  assert.strictEqual(calls.at(-1).args[1], options);
});
