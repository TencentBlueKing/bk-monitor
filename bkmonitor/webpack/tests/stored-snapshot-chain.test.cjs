const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { spawnSync } = require('node:child_process');
const test = require('node:test');
const { layout, timelineHarness, history, load } = require('./helpers/topology-history-harness.cjs');
const fixtures = path.join(__dirname, 'fixtures/topology');
function render(payload) {
  const result = spawnSync(process.env.PYTHON || 'python3', [path.join(__dirname, 'helpers/render-stored-snapshots.py')], { input: JSON.stringify(payload), encoding: 'utf8', maxBuffer: 32 * 1024 * 1024 });
  assert.equal(result.status, 0, result.stderr);
  return JSON.parse(result.stdout);
}
function visible(items) { return items.filter(item => item._cfg.visible).map(item => item.model.id).sort(); }
async function verify(payload) {
  const original = JSON.stringify(payload);
  const result = render(payload);
  assert.equal(result.history.status, undefined);
  assert.ok(result.history.latest.nodes.length > 0, 'positive snapshot lost all visible nodes');
  assert.ok(result.history.latest.edges.length > 0, 'positive snapshot lost all visible edges');
  if (payload.expected_frames) assert.deepEqual(result.full.full.map(frame => ({ nodes: frame.content.nodes.length, edges: frame.content.edges.length })), payload.expected_frames);
  assert.deepEqual(result.history.latest, result.latest.latest);
  assert.deepEqual(result.history.complete, result.full.complete);
  for (const response of [result.history, result.latest]) {
    const { graph } = await layout(response);
    const positioned = new Map();
    const walk = node => { positioned.set(node.id, node); (node.children || []).forEach(walk); }; walk(graph);
    for (const node of response.complete.nodes) {
      assert.ok(positioned.has(node.id), `missing layout node ${node.id}`);
      assert.ok(Number.isFinite(positioned.get(node.id).x));
      assert.ok(Number.isFinite(positioned.get(node.id).y));
    }
  }
  const h = timelineHarness(result.history);
  const order = result.full.full.map((_, index) => index);
  for (const index of [...order, ...order.toReversed()]) {
    h.timeline.handleTimelineChange(index);
    const expected = result.full.full[index].content;
    assert.deepEqual(visible(h.nodes), expected.nodes.map(node => node.id).sort());
    assert.deepEqual(visible(h.edges), expected.edges.map(load('snapshot-analysis.ts').topologyEdgeId).sort());
  }
  assert.equal(JSON.stringify(payload), original);
  return result;
}
for (const name of ['graph-walk', 'graph-walk-history', 'small-model', 'small-model-unified']) {
  test(`stored ${name}: resource -> history merge -> actual ELK -> timeline forwards/backwards`, async () => {
    await verify(JSON.parse(fs.readFileSync(path.join(fixtures, name + '.json'), 'utf8')));
  });
}
test('stored node deletion and reappearance survive merge, layout and reverse playback', async () => {
  const { snapshots: [first] } = JSON.parse(fs.readFileSync(path.join(fixtures, 'graph-walk.json'), 'utf8'));
  const absent = structuredClone(first);
  const removed = absent.incident_propagation_graph.entities.pop().entity_id;
  absent.incident_propagation_graph.edges = absent.incident_propagation_graph.edges.filter(e => e.source_id !== removed && e.target_id !== removed);
  await verify({ snapshots: [first, absent, first, absent, first] });
});
test('empty result, missing synchronized payload and invalid graph are distinct API/display states', () => {
  const { snapshots: [base] } = JSON.parse(fs.readFileSync(path.join(fixtures, 'small-model.json'), 'utf8'));
  const empty = structuredClone(base); empty.incident_propagation_graph = { entities: [], edges: [] };
  const missing = structuredClone(base); delete missing.incident_propagation_graph;
  const dangling = structuredClone(base); dangling.incident_propagation_graph.edges[0].target_id = 'absent';
  const duplicate = structuredClone(base); duplicate.incident_propagation_graph.entities.push(duplicate.incident_propagation_graph.entities[0]);
  const rank = structuredClone(base); rank.incident_propagation_graph.entities[0].rank_name = 'absent';
  const malformed = structuredClone(base); delete malformed.incident_propagation_graph.entities[0].entity_name;
  const invalidEndpoint = structuredClone(base); invalidEndpoint.incident_propagation_graph.edges[0].source_id = [];
  for (const content of [dangling, duplicate, rank, malformed, invalidEndpoint]) assert.equal(render({ snapshots: [content] }).history.status, 'INVALID_DATA');
  assert.equal(render({ snapshots: [missing] }).history.status, 'SYNC_FAILED');
  assert.equal(render({ snapshots: [] }).history.status, 'NO_DATA');
  assert.equal(render({ snapshots: [empty] }).history.complete.nodes.length, 0);
  const { topologyFailure } = load('graph/topology-status.ts');
  const states = ['no_result', 'sync_failed', 'invalid_data', 'layout_failed', 'query_failed'].map(reason => topologyFailure(reason, x => x));
  assert.equal(new Set(states.map(state => state.title)).size, 5);
  assert.equal(states[0].isNoData, true);
  assert.ok(states.slice(1).every(state => state.isError && !state.isNoData));
});
// Private archived inputs can use this same chain locally without entering Git or CI artifacts.
if (process.env.SNAPSHOT_REGRESSION_INPUT) test('private stored snapshot regression', async () => {
  await verify(JSON.parse(fs.readFileSync(process.env.SNAPSHOT_REGRESSION_INPUT, 'utf8')));
});
