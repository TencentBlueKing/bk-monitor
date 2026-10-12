const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');

const source = fs.readFileSync(
  path.join(
    __dirname,
    '../src/monitor-pc/pages/monitor-k8s/components/k8s-charts/tools/promql-generator/gpu-promql-generator.ts'
  ),
  'utf8'
);

test('GPU workload query prefers pod relation and keeps CPU fallback', () => {
  assert.match(source, /pod_with_workload_relation\{\$\{filter\}\} \$time_shift/);
  assert.match(source, /unless on\(bcs_cluster_id, namespace, pod_name\)/);
  assert.match(source, /\* on\(bcs_cluster_id, pod_name, namespace\)/);
  assert.match(source, /container_cpu_usage_seconds_total/);
});
