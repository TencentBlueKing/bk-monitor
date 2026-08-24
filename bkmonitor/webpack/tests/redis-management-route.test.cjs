const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');

process.env.TS_NODE_PROJECT = path.resolve(__dirname, '../src/monitor-pc/tsconfig.json');
process.env.TS_NODE_COMPILER_OPTIONS = JSON.stringify({
  module: 'commonjs',
  moduleResolution: 'node',
});
require('ts-node/register/transpile-only');

const {
  buildBoundaryDraft,
  buildSparklineSegments,
  calculateMarkerHeight,
  calculateMemoryScale,
  canAccessRedisManagement,
  canEditBoundary,
  coverageBetween,
  costBetween,
} = require('../src/monitor-pc/pages/redis-management/route-model.ts');

test('累计成本前缀支持任意策略范围的常数次查询', () => {
  const prefix = [
    {
      strategyId: 100,
      lowerBytes: 1000,
      upperBytes: 1500,
      peakMembers: 10,
      measuredCount: 1,
      unmeasuredCount: 0,
    },
    {
      strategyId: 1200,
      lowerBytes: 3000,
      upperBytes: 4500,
      peakMembers: 30,
      measuredCount: 2,
      unmeasuredCount: 0,
    },
    {
      strategyId: 1800,
      lowerBytes: 6000,
      upperBytes: 9000,
      peakMembers: 60,
      measuredCount: 3,
      unmeasuredCount: 0,
    },
  ];

  assert.deepEqual(costBetween(prefix, 101, 1800), {
    lowerBytes: 5000,
    upperBytes: 7500,
    peakMembers: 50,
    measuredCount: 2,
    unmeasuredCount: 0,
  });
});

test('范围覆盖前缀不会把未测量策略当成零成本', () => {
  const prefix = [
    {
      strategyId: 100,
      lowerBytes: 1000,
      upperBytes: 1500,
      peakMembers: 10,
      measuredCount: 1,
      unmeasuredCount: 0,
    },
    {
      strategyId: 500,
      lowerBytes: 1000,
      upperBytes: 1500,
      peakMembers: 10,
      measuredCount: 1,
      unmeasuredCount: 1,
    },
  ];

  assert.deepEqual(coverageBetween(prefix, 101, 500), { measuredCount: 0, unmeasuredCount: 1 });
});

test('拖动边界分别计算切换期双占峰值与稳定态', () => {
  const routes = [
    { from: 1, to: 999, nodeId: 1 },
    { from: 1000, to: 1999, nodeId: 2 },
  ];
  const nodes = {
    1: { currentBytes: 10000, max3hBytes: 12000 },
    2: { currentBytes: 20000, max3hBytes: 23000 },
  };
  const prefix = [
    {
      strategyId: 1000,
      lowerBytes: 1000,
      upperBytes: 1500,
      peakMembers: 10,
      measuredCount: 1,
      unmeasuredCount: 0,
    },
    {
      strategyId: 1099,
      lowerBytes: 3000,
      upperBytes: 4500,
      peakMembers: 30,
      measuredCount: 2,
      unmeasuredCount: 0,
    },
  ];

  const draft = buildBoundaryDraft(routes, 0, 1099, prefix, nodes);

  assert.equal(draft.sourceNodeId, 2);
  assert.equal(draft.targetNodeId, 1);
  assert.deepEqual(draft.range, { from: 1000, to: 1099 });
  assert.deepEqual(draft.transition[1], { currentBytes: 14500, max3hBytes: 16500 });
  assert.deepEqual(draft.transition[2], { currentBytes: 20000, max3hBytes: 23000 });
  assert.deepEqual(draft.steady[1], { currentBytes: 14500, max3hBytes: 16500 });
  assert.deepEqual(draft.steady[2], { currentBytes: 15500, max3hBytes: 18500 });
  assert.equal(draft.measuredCount, 2);
  assert.equal(draft.unmeasuredCount, 0);
});

test('热策略内存刻度根据当前数据上调而不是写死 256 MiB', () => {
  const mib = 1024 * 1024;
  assert.equal(calculateMemoryScale([80 * mib, 300 * mib, 620 * mib]), 1024 * mib);
  assert.equal(calculateMemoryScale([...Array.from({ length: 95 }, (_, index) => (index + 1) * mib), 800 * mib]), 1024 * mib);
  assert.equal(calculateMarkerHeight(200 * mib, 400 * mib), calculateMarkerHeight(100 * mib, 400 * mib) * 2);
});

test('无效拓扑或停用节点不能进入边界编辑', () => {
  const routes = [
    { from: 1, to: 999, nodeId: 1 },
    { from: 1000, to: 1999, nodeId: 2 },
  ];
  assert.equal(canEditBoundary(routes, 0, [1, 2], true), true);
  assert.equal(canEditBoundary(routes, 0, [1], true), false);
  assert.equal(canEditBoundary(routes, 0, [1, 2], false), false);
});

test('趋势折线按真实时间定位并在缺口处分段', () => {
  assert.deepEqual(
    buildSparklineSegments([
      [100, 1000],
      [200, 1060],
      [null, 1120],
      [150, 1180],
      [250, 1240],
    ]),
    ['0.0,38.0 45.0,15.3', '135.0,26.7 180.0,4.0']
  );
});

test('菜单权限同时要求平台管理员和全局管理权限', () => {
  assert.equal(canAccessRedisManagement(true, [{ isAllowed: true }]), true);
  assert.equal(canAccessRedisManagement(true, [{ isAllowed: false }]), false);
  assert.equal(canAccessRedisManagement(false, [{ isAllowed: true }]), false);
  assert.equal(canAccessRedisManagement(false, [{ isAllowed: false }]), false);
});

test('正式页面不包含 Demo 和特定环境取证话术', () => {
  const source = fs.readFileSync(
    path.resolve(__dirname, '../src/monitor-pc/pages/redis-management/redis-management.tsx'),
    'utf8'
  );
  assert.doesNotMatch(source, /bkop|bkm-cli|文件导入|本地快照|96\.77|\bDemo\b|P\s*\/\s*I/i);
});

test('Redis 管理入口不进入绕过权限过滤的全局收藏列表', () => {
  const source = fs.readFileSync(path.resolve(__dirname, '../src/monitor-pc/router/router-config.ts'), 'utf8');
  assert.doesNotMatch(source, /GLOBAL_FEATURE_LIST[\s\S]*redis-management/);
});
