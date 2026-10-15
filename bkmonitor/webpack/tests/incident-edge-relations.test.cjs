const assert = require('node:assert/strict');
const test = require('node:test');
const { relations, drawMain, drawResource, animationStarts, renderEdge, renderList, readMetrics } =
  require('./helpers/incident-edge-harness.cjs');
const edge = (edge_type, properties = {}, is_anomaly = true) => ({
  id: 'edge',
  source: 'a',
  target: 'b',
  source_name: 'a',
  target_name: 'b',
  source_type: 'APMService',
  target_type: 'APMService',
  edge_type,
  properties,
  is_anomaly,
  anomaly_score: 1,
  events: [],
});

for (const [name, input, expected] of [
  [
    'explicit ownership overrides old call category',
    edge('ebpf_call', { relation_type: 'BELONG_TO', relation: 1 }),
    'dependency',
  ],
  [
    'explicit service call overrides old dependency category',
    edge('dependency', { relation_type: 'SERVICE_CALL', relation: 0 }),
    'call',
  ],
  ['numeric zero remains ownership', edge('spread', { relation: 0 }), 'dependency'],
  ['numeric one is a call', edge('spread', { relation: 1 }), 'call'],
  ['string zero remains ownership', edge('spread', { relation: '0' }), 'dependency'],
  ['string one is a call', edge('spread', { relation: '1' }), 'call'],
  ['small-model ownership string is supported', edge('spread', { relation: 'BELONG_TO' }), 'dependency'],
  ['small-model call string is supported', edge('spread', { relation: 'SERVICE_CALL' }), 'call'],
  ['legacy dependency is preserved', edge('dependency'), 'dependency'],
  ['legacy eBPF call is preserved', edge('ebpf_call'), 'call'],
  ['untyped spread preserves propagation rather than claiming a call', edge('spread'), 'propagation'],
  [
    'unknown explicit relationship never falls back to call',
    edge('ebpf_call', { relation_type: 'FUTURE', relation: 1 }),
    'unknown',
  ],
  ['unknown category is not guessed', edge('future'), 'unknown'],
  ['boolean relation is not coerced to zero', edge('spread', { relation: false }), 'unknown'],
  ['array relation is not coerced to zero', edge('spread', { relation: [] }), 'unknown'],
  ['missing relation falls back to legacy category', edge('dependency', { relation: null }), 'dependency'],
]) {
  test(name, () => {
    const before = structuredClone(input);
    assert.equal(relations.getEdgeRelation(input), expected);
    assert.deepEqual(input, before);
  });
}

test('both production canvases derive direction from relation, never anomaly state', () => {
  for (const input of [
    edge('spread', { relation: 0 }),
    edge('spread', { relation: 1 }),
    edge('spread'),
    edge('future'),
  ]) {
    const directed = ['call', 'propagation'].includes(relations.getEdgeRelation(input));
    for (const draw of [drawMain, drawResource]) {
      const normal = draw({ ...input, is_anomaly: false });
      const anomalous = draw(input);
      assert.equal(Boolean(normal.style.endArrow), directed);
      assert.equal(Boolean(anomalous.style.endArrow), directed);
      assert.notEqual(normal.style.stroke, anomalous.style.stroke);
      assert.notDeepEqual(normal.style.lineDash, anomalous.style.lineDash);
      assert.equal(anomalous.edge_type, input.edge_type);
      assert.deepEqual(anomalous.properties, input.properties);
    }
  }
});

test('sidebar and aggregate member use their own explicit relation including zero', async () => {
  for (const [input, label, directed] of [
    [edge('spread', { relation: 0 }), '从属关系', false],
    [edge('dependency', { relation_type: 'SERVICE_CALL' }), '调用关系', true],
    [edge('spread'), '传播关系', true],
    [edge('ebpf_call', { relation_type: 'FUTURE' }), '未知关系', false],
  ]) {
    const html = await renderEdge(input);
    assert.ok(html.includes(`关系类型：${label}`), html);
    assert.equal(html.includes('edpf-link-arrow'), directed);
    const list = await renderList(input);
    assert.ok(list.includes(`title="${label}"`), list);
    assert.equal(list.includes('call-edge'), directed);
  }
});

test('animation uses the same relation semantics and requires saved events and anomaly', () => {
  const events = [{ direction: 'reverse' }];
  assert.equal(animationStarts({ ...edge('ebpf_call', { relation_type: 'BELONG_TO' }), events }), 0);
  assert.equal(animationStarts({ ...edge('spread', { relation: 1 }), events }), 1);
  assert.equal(animationStarts({ ...edge('spread'), events }), 1);
  assert.equal(animationStarts({ ...edge('spread', { relation: 1 }, false), events }), 0);
  assert.equal(animationStarts(edge('spread', { relation: 1 })), 0);
});

test('legacy parallel edges keep their own saved metrics without any live fallback query', async () => {
  const call = {
    ...edge('spread', { relation: 1 }),
    events: [
      {
        metric_name: 'errors',
        event_name: 'Errors',
        time_series: [
          [1700000000000, 2],
          [1700000060000, 0],
        ],
      },
    ],
  };
  const ownership = edge('dependency', { relation: 0 });
  const before = JSON.stringify([call, ownership]);
  const callResult = await readMetrics(call);
  const ownershipResult = await readMetrics(ownership);
  assert.equal(callResult.metrics[0].metric_name, 'errors');
  assert.deepEqual(callResult.metrics[0].time_series.default.datapoints, call.events[0].time_series);
  assert.deepEqual(ownershipResult.metrics, []);
  assert.deepEqual([...callResult.requests, ...ownershipResult.requests], []);
  assert.equal(JSON.stringify([call, ownership]), before);
});
