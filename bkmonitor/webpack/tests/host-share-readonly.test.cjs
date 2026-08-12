const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const ts = require('typescript');

const readSource = relativePath => fs.readFileSync(path.resolve(__dirname, relativePath), 'utf8');
const loadTsModule = relativePath => {
  const source = readSource(relativePath);
  const code = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  }).outputText;
  const module = { exports: {} };
  Function('exports', 'module', code)(module.exports, module);
  return module.exports;
};

test('主机分享组件通过 APP_READONLY_KEY 消费应用只读态', () => {
  const source = readSource('../src/trace/pages/host/components/temporary-share/temporary-share.tsx');

  assert.match(source, /useAppReadonlyInject/);
  assert.match(source, /const readonly = useAppReadonlyInject\(\) \?\? false/);
  assert.doesNotMatch(source, /inject\(['"]readonly['"]/);
});

test('主机页将应用只读态下传到详情、拓扑和内容区', () => {
  const source = readSource('../src/trace/pages/host/host.tsx');

  assert.match(source, /const readonly = useAppReadonlyInject\(\) \?\? false/);
  assert.match(source, /<HostTopoTree[\s\S]*readonly=\{this\.readonly\}/);
  assert.match(source, /<HostContentTabs[\s\S]*readonly=\{this\.readonly\}/);
  assert.match(source, /<HostDetailView[\s\S]*readonly=\{this\.readonly\}/);
});

test('只读态禁止拓扑和主机列表切换目标', () => {
  const topoSource = readSource('../src/trace/pages/host/components/host-topo-tree/host-topo-tree.tsx');
  const contentSource = readSource('../src/trace/pages/host/components/host-content-tabs/host-content-tabs.tsx');

  assert.match(topoSource, /if \(props\.readonly\) \{[\s\S]*return;/);
  assert.match(contentSource, /if \(props\.readonly\) \{[\s\S]*return;/);
});

test('只读态隐藏分享和视图分组写入口', () => {
  const locationSource = readSource('../src/trace/pages/host/components/host-location-bar/host-location-bar.tsx');
  const toolbarSource = readSource('../src/trace/pages/host/components/host-metric/metric-toolbar.tsx');

  assert.match(locationSource, /!props\.readonly && \([\s\S]*<TemporaryShare/);
  assert.match(toolbarSource, /!readonly && \([\s\S]*metric-toolbar__setting/);
});

test('只读态隐藏主机置顶写入口', () => {
  const contentSource = readSource('../src/trace/pages/host/components/host-content-tabs/host-content-tabs.tsx');
  const listSource = readSource('../src/trace/pages/host/components/host-list/host-list.tsx');
  const tableSource = readSource('../src/trace/pages/host/components/host-list/host-list-table.tsx');

  assert.match(contentSource, /<HostList[\s\S]*readonly=\{props\.readonly\}/);
  assert.match(listSource, /<HostListTable[\s\S]*readonly=\{props\.readonly\}/);
  assert.match(tableSource, /!props\.readonly\s*&&\s*\([\s\S]*host-table-ip-mark/);
});

test('只读态关闭主机图表外跳菜单和主机列表外跳交互', () => {
  const chartSource = readSource('../src/trace/pages/host/components/dashbords/components/time-series-card.tsx');
  const chartTitleSource = readSource('../src/trace/plugins/components/chart-title.tsx');
  const tableSource = readSource('../src/trace/pages/host/components/host-list/host-list-table.tsx');

  assert.match(chartSource, /const readonly = useAppReadonlyInject\(\) \?\? false/);
  assert.match(
    chartSource,
    /menuList=\{this\.readonly \? \[\] : \['more', 'explore', 'drill-down', 'relate-alert'\]\}/
  );
  assert.match(chartSource, /showAddMetric=\{!this\.readonly\}/);
  assert.match(chartSource, /showMore=\{!this\.readonly\}/);
  assert.match(chartSource, /showMetricAlarm=\{!this\.readonly\}/);
  assert.match(chartTitleSource, /showMetricAlarm:[\s\S]*default: true/);
  assert.match(chartTitleSource, /if \(!props\.showMetricAlarm \|\| props\.metrics\?\.length !== 1\) return;/);
  assert.match(chartTitleSource, /props\.showMetricAlarm && props\.metrics\?\.length === 1/);
  assert.match(tableSource, /const handleTipsMouseenter = [\s\S]*if \(props\.readonly\) \{[\s\S]*return;/);
  assert.match(tableSource, /onClick=\{props\.readonly \? undefined : \(\) => handleGoEventCenter\(row\)\}/);
  assert.match(tableSource, /onMouseenter=\{props\.readonly \? undefined : e => hasAlarm/);
});

test('分享 token formatter 写入规范 host 或 topo scope', () => {
  const source = readSource('../src/trace/pages/host/components/host-location-bar/host-location-bar.tsx');

  assert.match(source, /target_type: 'host', bk_host_id: node\.bk_host_id/);
  assert.match(source, /target_type: 'topo', bk_obj_id: node\.bk_obj_id, bk_inst_id: node\.bk_inst_id/);
  assert.match(source, /data\.scope = scope/);
  assert.match(source, /shareTargetType: scope\.target_type/);
});

test('分享页首次列表请求从路由恢复 scope 且不被后续选中节点覆盖', () => {
  const { resolveHostRequestScope } = loadTsModule('../src/trace/pages/host/utils/share-scope.ts');
  const hostQuery = { shareTargetType: 'host', shareBkHostId: '100' };
  const topoQuery = { shareTargetType: 'topo', shareBkObjId: 'module', shareBkInstId: '10' };

  assert.deepEqual(resolveHostRequestScope(true, hostQuery, null), { bk_host_id: 100 });
  assert.deepEqual(resolveHostRequestScope(true, topoQuery, null), { bk_inst_id: 10, bk_obj_id: 'module' });
  assert.deepEqual(resolveHostRequestScope(true, hostQuery, { bk_host_id: 101 }), { bk_host_id: 100 });
  assert.deepEqual(resolveHostRequestScope(false, hostQuery, null), {});
});

test('分享页数据请求携带 scope 且进程请求携带主机 ID', () => {
  const topoSource = readSource('../src/trace/pages/host/composables/use-host-topo-tree.ts');
  const hostSource = readSource('../src/trace/pages/host/host.tsx');
  const listSource = readSource('../src/trace/pages/host/composables/use-host-list.ts');
  const processSource = readSource('../src/trace/pages/host/composables/use-process-list.ts');

  assert.match(topoSource, /getHostTopoTreeByBizId\(window\.cc_biz_id, shareScope\.value\)/);
  assert.match(topoSource, /resolveHostRequestScope\(readonly, route\.query, null\)/);
  assert.match(hostSource, /useHostTopoTree\(nodeId, readonly\)/);
  assert.match(listSource, /resolveHostRequestScope\(options\.readonly, route\.query, selectedNode\.value\)/);
  assert.match(processSource, /bk_host_id: host\.bk_host_id/);
});
