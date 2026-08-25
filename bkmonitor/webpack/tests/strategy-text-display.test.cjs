const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const ts = require('typescript');

function loadTextDisplayUtils() {
  const filename = path.resolve(__dirname, '../src/monitor-pc/pages/text-display-utils.ts');
  if (!fs.existsSync(filename)) {
    return {};
  }

  const source = fs.readFileSync(filename, 'utf8');
  const { outputText } = ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.CommonJS,
      target: ts.ScriptTarget.ES2020,
    },
    fileName: filename,
  });
  const loadedModule = { exports: {} };
  const executeModule = new Function('exports', 'module', outputText);
  executeModule(loadedModule.exports, loadedModule);
  return loadedModule.exports;
}

const textDisplayUtils = loadTextDisplayUtils();

test('搜索结果名称按多个关键词拆分为纯文本片段', () => {
  assert.equal(typeof textDisplayUtils.splitHighlightFragments, 'function', '缺少纯文本高亮方法');

  const fragments = textDisplayUtils.splitHighlightFragments('CPU <metric> usage', 'cpu <metric>');

  assert.deepEqual(fragments, [
    { text: 'CPU', highlight: true, start: 0 },
    { text: ' ', highlight: false, start: 3 },
    { text: '<metric>', highlight: true, start: 4 },
    { text: ' usage', highlight: false, start: 12 },
  ]);
});

test('搜索关键词中的正则特殊字符按原文匹配', () => {
  assert.equal(typeof textDisplayUtils.splitHighlightFragments, 'function', '缺少纯文本高亮方法');

  const fragments = textDisplayUtils.splitHighlightFragments('load[5m] load5m', 'load[5m]');

  assert.deepEqual(fragments, [
    { text: 'load[5m]', highlight: true, start: 0 },
    { text: ' load5m', highlight: false, start: 8 },
  ]);
});

test('策略描述提示使用纯文本并保留多行内容', () => {
  assert.equal(typeof textDisplayUtils.getItemDescriptionTooltip, 'function', '缺少策略描述提示配置');

  const tooltip = textDisplayUtils.getItemDescriptionTooltip([
    { val: 'sum(rate(metric[5m]))' },
    { val: '<metric data-kind="sample">cpu</metric>' },
  ]);

  assert.deepEqual(tooltip, {
    allowHTML: false,
    content: 'sum(rate(metric[5m]))\n<metric data-kind="sample">cpu</metric>',
    extCls: 'strategy-item-description-tooltips',
  });
});

test('仪表盘搜索结果标题使用纯文本片段展示', () => {
  const source = fs.readFileSync(
    path.resolve(__dirname, '../src/monitor-pc/pages/grafana/dashboard-container/dashboard-aside.tsx'),
    'utf8'
  );

  assert.doesNotMatch(source, /domPropsInnerHTML/);
  assert.match(source, /splitHighlightFragments\(item\.title,\s*this\.keywork\)/);
  assert.match(source, /\{fragment\.text\}/);
});

test('标签搜索结果使用纯文本片段展示', () => {
  const source = fs.readFileSync(
    path.resolve(__dirname, '../src/monitor-pc/components/multi-label-select/multi-label-select.tsx'),
    'utf8'
  );

  assert.doesNotMatch(source, /domPropsInnerHTML/);
  assert.match(source, /splitHighlightFragments\(id,\s*this\.removeSpacesInputValue\)/);
  assert.match(source, /class='hl'/);
});

test('维度下拉与告警组下拉使用纯文本名称', () => {
  const dimensionSource = fs.readFileSync(
    path.resolve(
      __dirname,
      '../src/monitor-pc/pages/strategy-config/strategy-config-set-new/monitor-data/monitor-data-input.tsx'
    ),
    'utf8'
  );
  const alarmGroupSource = fs.readFileSync(
    path.resolve(
      __dirname,
      '../src/monitor-pc/pages/strategy-config/strategy-config-set/strategy-alarm-group/strategy-alarm-group.vue'
    ),
    'utf8'
  );

  assert.doesNotMatch(dimensionSource, /domPropsInnerHTML/);
  assert.match(dimensionSource, /\{node\.name\}/);
  assert.doesNotMatch(alarmGroupSource, /domPropsInnerHTML|highlightKeyword/);
  assert.match(alarmGroupSource, /node\.name/);
});

test('事件维度提示使用纯文本并保留多行内容', () => {
  assert.equal(typeof textDisplayUtils.getKeyValueTooltip, 'function', '缺少键值提示配置');

  const tooltip = textDisplayUtils.getKeyValueTooltip([
    { key: 'host', value: '<img src=x onerror=alert(1)>' },
    { key: 'disk', value: 'sda' },
  ]);

  assert.deepEqual(tooltip, {
    allowHTML: false,
    content: 'host：<img src=x onerror=alert(1)>\ndisk：sda',
    extCls: 'event-tags-text-tooltips',
  });

  const source = fs.readFileSync(
    path.resolve(__dirname, '../src/fta-solutions/pages/event/event-detail/related-events.tsx'),
    'utf8'
  );
  assert.doesNotMatch(source, /allowHTML:\s*true/);
  assert.match(source, /getKeyValueTooltip/);
});

test('智能检测状态文案按数字拆分为纯文本片段', () => {
  assert.equal(typeof textDisplayUtils.splitNumberHighlightFragments, 'function', '缺少数字高亮拆分方法');

  const fragments = textDisplayUtils.splitNumberHighlightFragments('模型准备中，预计 3.5 分钟 <script>');

  assert.deepEqual(fragments, [
    { text: '模型准备中，预计 ', highlight: false, start: 0 },
    { text: '3.5', highlight: true, start: 9 },
    { text: ' 分钟 <script>', highlight: false, start: 12 },
  ]);
});

test('智能检测状态条不再使用 innerHTML', () => {
  const files = [
    '../src/monitor-pc/pages/strategy-config/strategy-config-set-new/detection-rules/components/intelligent-detect/intelligent-detect.tsx',
    '../src/monitor-pc/pages/strategy-config/strategy-config-set-new/detection-rules/components/time-series-forecast/time-series-forecast.tsx',
    '../src/monitor-pc/pages/strategy-config/strategy-config-set-new/detection-rules/components/abnormal-cluster/abnormal-cluster.tsx',
  ];

  files.forEach(relativePath => {
    const source = fs.readFileSync(path.resolve(__dirname, relativePath), 'utf8');
    assert.doesNotMatch(source, /domPropsInnerHTML/);
    assert.match(source, /splitNumberHighlightFragments\(this\.tipsData\.message\)/);
  });
});
