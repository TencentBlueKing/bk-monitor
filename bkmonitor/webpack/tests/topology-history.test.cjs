const assert = require('node:assert/strict');
const test = require('node:test');
const { history, layout, timelineHarness } = require('./helpers/topology-history-harness.cjs');
const node = (id, comboId) => ({ id, comboId, entity: { rank: { rank_category: { category_id: Number(comboId), category_alias: 'category', category_name: 'category' } } } });
const service = node('service', '0');
const pod = node('pod', '1');
const edge = { source: 'service', target: 'pod', edge_type: 'dependency' };
const frame = (nodes, edges) => ({ create_time: 1, content: { nodes, edges, sub_combos: [] } });
function response() {
  return { latest: { nodes: [service], edges: [], combos: [{ id: '0' }] }, complete: { nodes: [service, { ...pod, is_deleted: true }], edges: [{ ...edge, is_deleted: true }], sub_combos: [] }, diff: [frame([service, pod], [edge]), frame([{ ...pod, is_deleted: true }], [{ ...edge, is_deleted: true }]), frame([pod], [edge]), frame([{ ...pod, is_deleted: true }], [{ ...edge, is_deleted: true }])] };
}
test('historical group missing from latest is restored and ELK lays out every historical node', async () => {
  const input = response(); const frozen = JSON.stringify(input);
  const { graph } = await layout(input);
  const ids = new Set(); const walk = n => { ids.add(n.id); (n.children ?? []).forEach(walk); }; walk(graph);
  assert.ok(ids.has('pod')); assert.ok(ids.has('service'));
  assert.equal(JSON.stringify(input), frozen);
});
test('complete categories take precedence and unknown categories/dangling endpoints fail explicitly', () => {
  const r = response(); r.complete.combos = [{ id: '0', label: 'stored' }, { id: '1' }];
  assert.equal(history.historyCombos(r.complete, r.latest)[0].label, 'stored');
  history.validateTopology(r.complete);
  assert.throws(() => history.validateTopology({ ...r.complete, edges: [{ source: 'service', target: 'absent' }] }), /INVALID_TOPOLOGY_HISTORY/);
  assert.throws(() => history.validateTopology({ nodes: [{ id: 'unknown', comboId: 'missing' }], combos: [] }), /INVALID_TOPOLOGY_HISTORY/);
});
test('timeline forward/backward hides deleted nodes and edges and restores reappearing nodes', () => {
  const h = timelineHarness(response());
  for (const index of [0, 1, 2, 3, 0, 3, 2, 1]) {
    h.timeline.handleTimelineChange(index);
    assert.equal(h.nodes.find(n => n.model.id === 'pod')._cfg.visible, index % 2 === 0);
    assert.equal(h.edges[0]._cfg.visible, index % 2 === 0);
  }
  assert.ok(h.cache.diff.every(f => f.showNodes.every(n => !Array.isArray(n))));
  assert.equal(h.cache.diff[1].showNodes.find(n => n.id === 'pod').is_deleted, undefined);
});
test('deleted or not-yet-created edge between visible nodes never appears in another frame', () => {
  const r = response(); r.diff = [frame([service, pod], []), frame([], [edge]), frame([], [{ ...edge, is_deleted: true }])];
  const h = timelineHarness(r);
  for (const i of [0, 1, 2, 0, 1]) { h.timeline.handleTimelineChange(i); assert.equal(h.edges[0]._cfg.visible, i === 1); }
});

test('layout rejection becomes a visible error instead of an unhandled blank canvas', async () => {
  const fs = require('node:fs');
  const path = require('node:path');
  const ts = require('typescript');
  const source = ts.createSourceFile('use-topo-graph.ts', fs.readFileSync(path.join(__dirname, '../src/trace/pages/failure/failure-topo/composables/use-topo-graph.ts'), 'utf8'), ts.ScriptTarget.Latest, true);
  let initializer;
  function visit(node) {
    if (ts.isVariableDeclaration(node) && node.name.getText(source) === 'renderGraph') initializer = node.initializer.getText(source);
    ts.forEachChild(node, visit);
  }
  visit(source);
  assert.ok(initializer);
  const code = ts.transpileModule(`const renderGraph = ${initializer};`, { compilerOptions: { target: ts.ScriptTarget.ES2020 } }).outputText;
  for (const sync of [true, false]) {
    const state = { errorData: { value: {} } };
    const render = new Function('getGraph', 'clearEdgeIntervals', 'topoData', 'state', 't', `${code}; return renderGraph;`)(
      () => ({}), () => {}, { resolveLayout() { if (sync) throw new Error('invalid'); return Promise.reject(new Error('invalid')); } }, state, x => x
    );
    await render({ nodes: [], edges: [], combos: [] });
    assert.equal(state.errorData.value.isError, true);
    assert.equal(state.errorData.value.msg, '图谱布局失败，请刷新重试');
  }
});
