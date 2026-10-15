const assert = require('node:assert/strict');
const test = require('node:test');
const {
  relations,
  drawMain,
  drawResource,
  animationStarts,
  renderEdge,
  renderList,
  readMetrics,
  renderNode,
} = require('./helpers/incident-edge-harness.cjs');
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

test('node details hide analysis metadata while preserving business attributes, root marker and metric input', async () => {
  const scores = [
    'legacy_anomaly_score',
    'self_anomaly',
    'propagated_impact',
    'explained_errors',
    'entrance_error_explanation_ratio',
  ].map(kind => ({ kind, value: 0 }));
  const model = {
    entity: {
      entity_id: 'service-a',
      entity_name: 'Service A',
      entity_type: 'APMService',
      rank_name: 'APMService',
      rank: { rank_category: { category_alias: 'Application' } },
      properties: { scores },
      tags: { BcsService: { name: 'Business Service' } },
    },
    is_feedback_root: true,
    bk_biz_id: 1,
    bk_biz_name: 'Business A',
    alert_ids: ['alert-a'],
    alert_display: { alert_name: 'Error alert' },
    graph_analysis: {
      protocol: 'graph-rca-snapshot',
      version: '1',
      producer: { engine: 'graph_walk' },
      root_causes: [{ entity_ref: 'service-a', rank: 1, scores, reason: 'Candidate explanation' }],
      evidence: [{ evidence_id: 'metric-a' }],
    },
  };
  const before = structuredClone(model);
  const result = await renderNode(model);
  for (const hidden of [
    'snapshot-analysis-info',
    '分析来源',
    '候选排名',
    '原始异常评分',
    '自身异常程度',
    '传播影响',
    '解释错误数',
    '入口错误解释比例',
    '分析依据',
    'Candidate explanation',
  ]) {
    assert.ok(!result.html.includes(hidden), hidden);
  }
  for (const visible of [
    'Service A',
    '根因',
    '包含告警',
    'Error alert',
    'Application',
    'APMService',
    'Business A',
    'Business Service',
    '指标',
    '关联边',
    'metric-view-boundary',
  ]) {
    assert.ok(result.html.includes(visible), visible);
  }
  assert.deepEqual(result.metricInput, model);
  result.clickAlert();
  assert.deepEqual(result.emitted, [['alert', model]]);
  assert.deepEqual(model, before);

  const linkedEdge = edge('dependency', { relation: 0 });
  const linked = await renderNode(model, 'linkedEdge', [linkedEdge]);
  assert.ok(linked.html.includes('从属关系'));
  assert.ok(linked.html.includes('关联边 (1)'));
  assert.equal(linked.metricInput, undefined);
  linked.clickEdge(linkedEdge);
  assert.deepEqual(linked.emitted, [['edge', linkedEdge]]);
});
