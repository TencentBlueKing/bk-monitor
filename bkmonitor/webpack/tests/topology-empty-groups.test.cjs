const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const { history, timelineHarness } = require('./helpers/topology-history-harness.cjs');

const node = (id, comboId) => ({ id, comboId, entity: { rank: { rank_category: { category_id: comboId } } } });
const service = node('service', '0');
const pod = node('pod', '1');
const laterPod = node('later-pod', '1');
const edge = { source: 'service', target: 'pod', edge_type: 'dependency' };
const frame = (nodes, edges = []) => ({ content: { nodes, edges, sub_combos: [] } });
function input() {
  return {
    latest: { nodes: [service], edges: [], combos: [{ id: '0' }] },
    complete: { nodes: [service, pod, laterPod], edges: [edge], combos: [{ id: '0' }, { id: '1' }, { id: '2' }], sub_combos: [] },
    diff: [frame([service, pod], [edge]), frame([{ ...pod, is_deleted: true }], [{ ...edge, is_deleted: true }]), frame([laterPod]), frame([{ ...laterPod, is_deleted: true }])],
  };
}
function assertFrame(h, index) {
  const nodes = [...history.frameNodes(h.cache.diff[index]).values()].filter(n => !n.is_deleted);
  const expectedGroups = new Set(nodes.map(n => String(n.comboId)));
  assert.deepEqual(h.nodes.filter(n => n.isVisible()).map(n => n.model.id).sort(), nodes.map(n => n.id).sort());
  for (const combo of h.combos) assert.equal(combo.isVisible(), expectedGroups.has(String(combo.model.id)), `frame ${index}: category ${combo.model.id}`);
}
test('latest hides empty categories; historical navigation restores only that frame’s Pods', () => {
  const r = input(); const original = JSON.stringify(r); const h = timelineHarness(r);
  for (const index of [3, 0, 1, 2, 3, 2, 0]) {
    h.timeline.handleTimelineChange(index, true);
    assertFrame(h, index);
  }
  assert.equal(JSON.stringify(r), original);
  assert.equal(h.combos.length, 3, 'history layout categories must not be deleted');
});
test('automatic playback updates top-level visibility, including deletion and reappearance', t => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  const h = timelineHarness(input());
  h.timeline.handlePlay({ value: true, timeline: true });
  assertFrame(h, 0);
  for (const i of [1, 2, 3]) { t.mock.timers.tick(600); assertFrame(h, i); }
  h.timeline.cleanupTimeline();
});
test('an entirely empty frame hides every root and can return to a populated frame', () => {
  const r = input(); r.diff.push(frame([{ ...service, is_deleted: true }]));
  const h = timelineHarness(r);
  h.timeline.handleTimelineChange(4, true); assertFrame(h, 4);
  h.timeline.handleTimelineChange(0, true); assertFrame(h, 0);
});
// Production archives stay local; run the same assertions on every independently rendered frame.
if (process.env.TOPOLOGY_ARCHIVE_DIR) test('private stored history: latest and all historical categories match saved frames', () => {
  const dir = process.env.TOPOLOGY_ARCHIVE_DIR;
  const r = JSON.parse(fs.readFileSync(path.join(dir, 'rebuilt-topology.private.json'), 'utf8'));
  const full = JSON.parse(fs.readFileSync(path.join(dir, 'full-frames.private.json'), 'utf8'));
  const original = JSON.stringify(r); const h = timelineHarness(r);
  for (const i of [full.length - 1, ...full.keys(), ...Array.from(full.keys()).reverse()]) {
    h.timeline.handleTimelineChange(i, true); assertFrame(h, i);
    assert.deepEqual(h.nodes.filter(n => n.isVisible()).map(n => n.model.id).sort(), full[i].nodes.map(n => n.id).sort());
    assert.deepEqual(h.combos.filter(c => c.isVisible()).map(c => String(c.model.id)).sort(), full[i].combos.map(c => String(c.id)).sort());
  }
  assert.equal(JSON.stringify(r), original);
});
