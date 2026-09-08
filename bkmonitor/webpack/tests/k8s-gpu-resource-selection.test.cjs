const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');

const source = fs.readFileSync(
  path.resolve(
    __dirname,
    '../src/monitor-pc/pages/monitor-k8s/components/k8s-charts/k8s-charts.tsx'
  ),
  'utf8'
);

test('GPU 图表使用 GPU 指标预选资源', () => {
  assert.match(
    source,
    /column:\s*this\.scene === SceneEnum\.GPU\s*\?\s*K8sTableColumnKeysEnum\.GPU_UTILIZATION\s*:\s*undefined/
  );
});
