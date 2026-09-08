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
  buildSparklinePoint,
  buildSparklineSegments,
  calculateMarkerHeight,
  calculateMemoryScale,
  calculateUsageScale,
  estimateNormalizedRedistribution,
  canAccessRedisManagement,
  buildRedisManagementForbiddenQuery,
  canEditBoundary,
  coverageBetween,
  costBetween,
  resolveRedisManagementAccess,
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

test('拖动边界只返回单次调整所需的范围、方向和迁移成本', () => {
  const routes = [
    { from: 1, to: 999, nodeId: 1 },
    { from: 1000, to: 1999, nodeId: 2 },
  ];
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

  const draft = buildBoundaryDraft(routes, 0, 1099, prefix);

  assert.equal(draft.sourceNodeId, 2);
  assert.equal(draft.targetNodeId, 1);
  assert.deepEqual(draft.range, { from: 1000, to: 1099 });
  assert.equal(draft.lowerBytes, 3000);
  assert.equal(draft.upperBytes, 4500);
  assert.equal(draft.measuredCount, 2);
  assert.equal(draft.unmeasuredCount, 0);
  assert.equal('transition' in draft, false);
  assert.equal('steady' in draft, false);
});

test('迁移成本按源节点策略成本占比归一到真实 3 小时峰值', () => {
  const estimate = estimateNormalizedRedistribution(4900, 730, 80, 100);

  assert.deepEqual(estimate, {
    movedBytes: 3920,
    sourceAfter: 980,
    targetAfter: 4650,
  });
  assert.equal(4900 - estimate.sourceAfter, estimate.targetAfter - 730);
});

test('成本证据无法形成有效占比时不返回虚假的零内存结果', () => {
  assert.equal(estimateNormalizedRedistribution(4900, 730, 100, 100), null);
  assert.equal(estimateNormalizedRedistribution(4900, 730, 101, 100), null);
  assert.equal(estimateNormalizedRedistribution(4900, 730, 80, 0), null);
  assert.equal(estimateNormalizedRedistribution(null, 730, 80, 100), null);
});

test('热策略内存刻度根据当前数据上调而不是写死 256 MiB', () => {
  const mib = 1024 * 1024;
  assert.equal(calculateMemoryScale([80 * mib, 300 * mib, 620 * mib]), 1024 * mib);
  assert.equal(
    calculateMemoryScale([...Array.from({ length: 95 }, (_, index) => (index + 1) * mib), 800 * mib]),
    1024 * mib
  );
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
  assert.equal(calculateUsageScale([0.036, 0.152]), 0.2);
  assert.deepEqual(buildSparklinePoint([[0.05, 1000], [0.15, 1060]], 1060, 0, 0.2), { x: 180, y: 12.5 });
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

test('Redis 管理入口跳转独立路由且不再渲染到设置弹层', () => {
  const source = fs.readFileSync(path.resolve(__dirname, '../src/monitor-pc/pages/nav-tools.tsx'), 'utf8');
  assert.match(source, /this\.\$router\.push\(\{\s*name:\s*'redis-management'\s*\}\)/);
  assert.doesNotMatch(source, /RedisManagement:\s*\(\)\s*=>/);
  assert.doesNotMatch(source, /activeSetting\s*===\s*'redis-management'/);
  assert.match(source, /menuList=\{this\.settingModalList\}/);
});

test('Redis 管理独立路由同时要求平台管理员和全局管理权限', () => {
  const routeSource = fs.readFileSync(
    path.resolve(__dirname, '../src/monitor-pc/router/platform-setting/index.ts'),
    'utf8'
  );
  const routerSource = fs.readFileSync(path.resolve(__dirname, '../src/monitor-pc/router/router.ts'), 'utf8');
  assert.match(routeSource, /path:\s*'\/redis-management'/);
  assert.match(routeSource, /page:\s*platformSettingAuth\.MANAGE_GLOBAL_SETTING/);
  assert.match(routeSource, /beforeEnter[\s\S]*resolveRedisManagementAccess/);
  assert.match(routeSource, /checkAllowedByActionIds/);
  assert.match(routeSource, /noNavBar:\s*true/);
  assert.match(routerSource, /'no-business'[\s\S]*'redis-management'[\s\S]*\.includes\(to\.name\)/);
});

test('Redis 管理独立路由的双权限查询失败时拒绝访问', async () => {
  let requests = 0;
  const allowed = async () => {
    requests += 1;
    return [{ isAllowed: true }];
  };
  assert.equal(await resolveRedisManagementAccess(false, allowed), false);
  assert.equal(requests, 0);
  assert.equal(await resolveRedisManagementAccess(true, allowed), true);
  assert.equal(requests, 1);
  assert.equal(await resolveRedisManagementAccess(true, async () => [{ isAllowed: false }]), false);
  assert.equal(
    await resolveRedisManagementAccess(true, async () => {
      throw new Error('permission unavailable');
    }),
    false
  );
});

test('非平台管理员拒绝访问时不携带会触发 IAM 自动恢复的参数', () => {
  assert.equal(buildRedisManagementForbiddenQuery(false, 'manage_global_setting', '/redis-management'), undefined);
  assert.deepEqual(buildRedisManagementForbiddenQuery(true, 'manage_global_setting', '/redis-management'), {
    actionId: 'manage_global_setting',
    fromUrl: 'redis-management',
  });
});

test('Redis 管理独立页面使用完整宽度', () => {
  const source = fs.readFileSync(
    path.resolve(__dirname, '../src/monitor-pc/pages/redis-management/redis-management.scss'),
    'utf8'
  );
  assert.match(source, /\.redis-management\s*\{[\s\S]*?width:\s*100%/);
  assert.match(source, /box-sizing:\s*border-box/);
});

test('成本快照时间在节点卡片和路由区域都有明确标签', () => {
  const source = fs.readFileSync(
    path.resolve(__dirname, '../src/monitor-pc/pages/redis-management/redis-management.tsx'),
    'utf8'
  );
  assert.match(source, /策略成本更新\s*\{formatDateTime\(evidenceTime/);
  assert.match(source, /策略成本更新：/);
});

test('热策略图层与路由条之间保留完整点位净空', () => {
  const source = fs.readFileSync(
    path.resolve(__dirname, '../src/monitor-pc/pages/redis-management/redis-management.scss'),
    'utf8'
  );
  assert.match(source, /\.redis-route-visual\s*\{[\s\S]*?height:\s*174px/);
  assert.match(source, /\.redis-hot-layer\s*\{[\s\S]*?inset:\s*12px 0 66px/);
  assert.match(source, /\.redis-route-track\s*\{[\s\S]*?height:\s*48px/);
});

test('热策略使用无延迟的框架 Tooltip', () => {
  const source = fs.readFileSync(
    path.resolve(__dirname, '../src/monitor-pc/pages/redis-management/redis-management.tsx'),
    'utf8'
  );
  assert.match(source, /v-bk-tooltips=\{\{[\s\S]*?content:\s*title[\s\S]*?delay:\s*\[0,\s*0\]/);
  assert.match(source, /aria-label=\{title\}/);
  assert.doesNotMatch(source, /title=\{title\}/);
});

test('拖动后只展示单一且可理解的内存变更预览', () => {
  const source = fs.readFileSync(
    path.resolve(__dirname, '../src/monitor-pc/pages/redis-management/redis-management.tsx'),
    'utf8'
  );
  assert.match(source, /3 小时采样峰值预估/);
  assert.match(source, /预计迁出/);
  assert.match(source, /预计迁入/);
  assert.match(source, /清理后预计回落至/);
  assert.match(source, /预计上升至/);
  assert.match(source, /源节点旧数据随清理周期逐步释放/);
  assert.match(source, /本次范围已估算/);
  assert.match(source, /this\.draft\.measuredCount/);
  assert.match(source, /this\.draft\.unmeasuredCount/);
  assert.match(source, /redis-route-live-preview/);
  const memoryPreview = source.match(/renderMemoryChange\(\)\s*\{([\s\S]*?)\n\s*renderDraft\(\)/)?.[1] ?? '';
  assert.match(memoryPreview, /3 小时采样峰值/);
  assert.match(memoryPreview, /draftMemoryEstimate/);
  assert.doesNotMatch(memoryPreview, /estimateMax3hMemoryRange/);
  assert.doesNotMatch(memoryPreview, /当前\s|调整后观测/);
  assert.doesNotMatch(source, /切换期|稳定后|不能作为容量安全结论/);
});

test('节点卡片解释使用趋势、峰值时间与样本覆盖', () => {
  const source = fs.readFileSync(
    path.resolve(__dirname, '../src/monitor-pc/pages/redis-management/redis-management.tsx'),
    'utf8'
  );
  assert.match(source, /最近 3 小时内存使用趋势/);
  assert.match(source, /峰值时间/);
  assert.match(source, /采样覆盖/);
  assert.match(source, /usage_trend/);
  assert.match(source, /max_3h_at/);
  assert.match(source, /页面数据/);
  assert.doesNotMatch(source, /formatAge/);
  assert.match(source, /页面数据 \{formatDateTime\(this\.data\.generated_at\)\}/);
  assert.match(source, /刷新失败，当前展示仍为上次数据/);
});

test('停用节点不展示在节点卡片和路由图例中', () => {
  const source = fs.readFileSync(
    path.resolve(__dirname, '../src/monitor-pc/pages/redis-management/redis-management.tsx'),
    'utf8'
  );
  assert.match(source, /get visibleNodes\(\)[\s\S]*?filter\(node => node\.is_enable\)/);
  assert.match(source, /get usageScale\(\)[\s\S]*?this\.visibleNodes\.flatMap/);
  assert.match(source, /redis-node-grid[\s\S]*?this\.visibleNodes\.map/);
  const routeAxis = source.match(/renderRouteAxis\(\)\s*\{([\s\S]*?)\n\s*renderMemoryChange\(\)/)?.[1] ?? '';
  assert.match(routeAxis, /redis-route-legend[\s\S]*?this\.visibleNodes\.map/);
});

test('策略路由区间明细始终展示全部节点范围并随草稿更新', () => {
  const source = fs.readFileSync(
    path.resolve(__dirname, '../src/monitor-pc/pages/redis-management/redis-management.tsx'),
    'utf8'
  );
  const routeAxis = source.match(/renderRouteAxis\(\)\s*\{([\s\S]*?)\n\s*renderMemoryChange\(\)/)?.[1] ?? '';
  assert.match(routeAxis, /redis-route-ranges/);
  assert.match(routeAxis, /this\.displayRoutes\.map\(route/);
  assert.match(routeAxis, /formatInteger\(route\.from\)/);
  assert.match(routeAxis, /formatInteger\(route\.to\)/);
  assert.match(routeAxis, /this\.draft\s*\?\s*'调整后路由区间'\s*:\s*'当前路由区间'/);
});

test('Redis 管理菜单具备正式路由翻译', () => {
  const source = fs.readFileSync(path.resolve(__dirname, '../src/monitor-pc/lang/route.ts'), 'utf8');
  assert.match(source, /'route-Redis 节点管理':\s*'Redis Node Management'/);
});
