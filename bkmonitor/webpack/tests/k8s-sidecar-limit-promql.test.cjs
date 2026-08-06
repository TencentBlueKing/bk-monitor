const assert = require('node:assert/strict');
const path = require('node:path');
const test = require('node:test');

process.env.TS_NODE_PROJECT = path.resolve(__dirname, '../src/monitor-pc/tsconfig.json');
process.env.TS_NODE_COMPILER_OPTIONS = JSON.stringify({
  module: 'commonjs',
  moduleResolution: 'node',
});
require('ts-node/register/transpile-only');

const { K8sTableColumnKeysEnum } = require('../src/monitor-pc/pages/monitor-k8s/typings/k8s-new.ts');
const {
  K8sBasePromqlGenerator,
} = require('../src/monitor-pc/pages/monitor-k8s/components/k8s-charts/tools/promql-generator/base-promql-generator.ts');
const {
  K8sPerformancePromqlGenerator,
} = require('../src/monitor-pc/pages/monitor-k8s/components/k8s-charts/tools/promql-generator/performance-promql-generator.ts');
const {
  K8sChartTargetsCreateTool,
} = require('../src/monitor-pc/pages/monitor-k8s/components/k8s-charts/tools/targets-create/k8s-chart-targets-create-tool.ts');

function createContext(groupByField) {
  return {
    bcs_cluster_id: 'BCS-K8S-00000',
    groupByField,
    resourceMap: new Map([
      [K8sTableColumnKeysEnum.NAMESPACE, 'default'],
      [K8sTableColumnKeysEnum.POD, 'demo-0'],
      [K8sTableColumnKeysEnum.CONTAINER, 'sidecar'],
      [K8sTableColumnKeysEnum.WORKLOAD, 'demo'],
      [K8sTableColumnKeysEnum.WORKLOAD_KIND, 'Deployment'],
      [K8sTableColumnKeysEnum.NODE, 'node-a'],
      [K8sTableColumnKeysEnum.CLUSTER, 'BCS-K8S-00000'],
    ]),
  };
}

function assertRunningSidecarLimit(promql, resource, unit, timeShift) {
  const regularLimit = `kube_pod_container_resource_limits\\{resource="${resource}",unit="${unit}",[^}]*\\}`;
  const initLimit = `kube_pod_init_container_resource_limits\\{resource="${resource}",unit="${unit}",[^}]*\\}`;
  const runningStatus = 'kube_pod_init_container_status_running\\{bcs_cluster_id="BCS-K8S-00000"\\}';

  assert.match(promql, new RegExp(regularLimit));
  assert.match(promql, new RegExp(initLimit));
  assert.match(promql, /\* on\(namespace,pod,container\) group_left\(\)/);
  assert.match(promql, /== 1/);

  if (timeShift) {
    assert.match(promql, new RegExp(`${regularLimit} \\$time_shift`));
    assert.match(promql, new RegExp(`${initLimit} \\$time_shift`));
    assert.match(promql, new RegExp(`${runningStatus} \\$time_shift == 1`));
  } else {
    assert.doesNotMatch(promql, /\$time_shift/);
    assert.match(promql, new RegExp(`${runningStatus} == 1`));
  }
}

test('limit 查询帮助方法合并普通容器与运行中的 init 容器', () => {
  assert.equal(typeof K8sBasePromqlGenerator.createContainerResourceLimit, 'function');

  assertRunningSidecarLimit(
    K8sBasePromqlGenerator.createContainerResourceLimit(createContext(K8sTableColumnKeysEnum.POD), true, true),
    'cpu',
    'core',
    true
  );
  assertRunningSidecarLimit(
    K8sBasePromqlGenerator.createContainerResourceLimit(createContext(K8sTableColumnKeysEnum.POD), false, false),
    'memory',
    'byte',
    false
  );
});

test('性能场景的 CPU 与内存 limit 使用率复用 Sidecar 兼容口径', () => {
  const generator = new K8sPerformancePromqlGenerator();

  assertRunningSidecarLimit(
    generator.generate('kube_pod_cpu_limits_ratio', createContext(K8sTableColumnKeysEnum.POD)),
    'cpu',
    'core',
    true
  );
  assertRunningSidecarLimit(
    generator.generate('kube_pod_memory_limits_ratio', createContext(K8sTableColumnKeysEnum.WORKLOAD)),
    'memory',
    'byte',
    true
  );
});

test('容器、节点与集群辅助线的 limit 复用 Sidecar 兼容口径', () => {
  const tool = new K8sChartTargetsCreateTool();
  const containerLimit = tool
    .getAuxiliaryLineQueryConfigsByMetric(
      'container_cpu_usage_seconds_total',
      createContext(K8sTableColumnKeysEnum.POD)
    )
    .find(item => item.alias === 'limit').promql;
  const nodeLimit = tool
    .getAuxiliaryLineQueryConfigsByMetric('node_memory_working_set_bytes', createContext(K8sTableColumnKeysEnum.NODE))
    .find(item => item.alias === 'limit').promql;
  const clusterLimit = tool
    .getAuxiliaryLineQueryConfigsByMetric('node_cpu_seconds_total', createContext(K8sTableColumnKeysEnum.CLUSTER))
    .find(item => item.alias === 'limit').promql;

  assertRunningSidecarLimit(containerLimit, 'cpu', 'core', false);
  assertRunningSidecarLimit(nodeLimit, 'memory', 'byte', false);
  assertRunningSidecarLimit(clusterLimit, 'cpu', 'core', false);
});
