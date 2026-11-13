const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const ts = require('typescript');

const root = path.resolve(__dirname, '../src/monitor-pc/pages/monitor-k8s/components');
const stop = new Error('captured scene-view request');
const calls = [];

async function capture(page, method, ...args) {
  const count = calls.length;
  await assert.rejects(page[method](...args), error => error === stop);
  assert.equal(calls.length, count + 1);
  return calls.at(-1);
}

function commonPage(filename, sceneId, type = 'detail', overrides = {}) {
  const Page = loadMethod(filename, 'handleGetPanelData');
  return Object.assign(new Page(), {
    sceneId, localSceneType: type, filters: { bk_biz_id: 2 }, $store: { getters: { bizId: 2 } },
    headerTitleChange() {}, currentTitle: '', hasOtherParams: false, selectorPanelPriority: false,
    isApmServiceOverview: false, isEnableMethodSelect: true, timeRange: ['now-1h', 'now'],
    ...overrides,
  });
}

function loadMethod(filename, methodName) {
  const file = path.join(root, filename);
  const source = ts.createSourceFile(file, fs.readFileSync(file, 'utf8'), ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  let method;
  function visit(node) {
    if (ts.isMethodDeclaration(node) && node.name?.getText(source) === methodName) method = node.getText(source);
    ts.forEachChild(node, visit);
  }
  visit(source);
  assert.ok(method, `${filename}:${methodName}`);
  const code = ts.transpileModule(`class Harness { ${method} } return Harness;`, {
    compilerOptions: { target: ts.ScriptTarget.ES2022 },
  }).outputText;
  return new Function('getSceneView', 'BookMarkModel', 'VariablesService', 'handleTransformToTimestamp', code)(
    params => { calls.push(structuredClone(params)); return Promise.resolve({ id: params.id, panels: [], name: '' }); },
    class { constructor() { throw stop; } },
    class { transformVariables(params) { return params; } },
    () => [100, 200],
  );
}

for (const file of ['common-page.tsx', 'common-page-new.tsx']) {
  test(`${file} declares support only for Kubernetes Pod detail and overview`, async () => {
    for (const type of ['detail', 'overview']) {
      const request = await capture(commonPage(file, 'kubernetes', type), 'handleGetPanelData', 'pod', false);
      assert.equal(request.scene_id, 'kubernetes');
      assert.equal(request.type, type);
      assert.equal(request.id, 'pod');
      assert.equal(request.supports_pod_memory_promql, true);
      if (file === 'common-page-new.tsx') assert.deepEqual([request.start_time, request.end_time], [100, 200]);
    }
    for (const [scene, id] of [['kubernetes', 'node'], ['host', 'pod'], ['host', 'host']]) {
      const request = await capture(commonPage(file, scene), 'handleGetPanelData', id, false);
      assert.equal('supports_pod_memory_promql' in request, false);
    }
  });

  test(`${file} uses the final scene and view identity after injected parameters`, async () => {
    const options = {
      hasOtherParams: true, selectorPanelPriority: true,
      currentTabData: { params: { scene_id: 'kubernetes', id: 'pod', namespace: 'qa' } },
    };
    const request = await capture(commonPage(file, 'host', 'detail', options), 'handleGetPanelData', 'host', false);
    assert.equal(request.supports_pod_memory_promql, true);
    assert.equal(request.namespace, 'qa');
    options.currentTabData.params = { scene_id: 'host', id: 'pod' };
    const other = await capture(commonPage(file, 'kubernetes', 'detail', options), 'handleGetPanelData', 'pod', false);
    assert.equal('supports_pod_memory_promql' in other, false);
  });
}

test('Split-panel requests support only for the Kubernetes Pod view', async () => {
  const Split = loadMethod('split-panel.tsx', 'handleGetSceneView');
  for (const [sceneId, relateTab, supported] of [
    ['kubernetes', 'pod_detail', true], ['kubernetes', 'pod_overview', true],
    ['kubernetes', 'node_detail', false], ['host', 'pod_detail', false],
  ]) {
    const request = await capture(Object.assign(new Split(), { sceneId, relateTab }), 'handleGetSceneView');
    assert.equal(request.is_split, true);
    assert.equal(request.scene_id, sceneId);
    assert.equal(request.supports_pod_memory_promql === true, supported);
    if (!supported) assert.equal('supports_pod_memory_promql' in request, false);
  }
});
