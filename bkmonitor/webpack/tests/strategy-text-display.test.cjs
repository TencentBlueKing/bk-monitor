const assert = require('node:assert/strict');
const path = require('node:path');
const test = require('node:test');

process.env.TS_NODE_PROJECT = path.resolve(__dirname, '../src/monitor-pc/tsconfig.json');
process.env.TS_NODE_COMPILER_OPTIONS = JSON.stringify({
  module: 'commonjs',
  moduleResolution: 'node',
});
require('ts-node/register/transpile-only');

const homeUtils = require('../src/monitor-pc/pages/home/new-home/utils.ts');
const strategyUtils = require('../src/monitor-pc/pages/strategy-config/util.ts');

test('搜索结果名称按多个关键词拆分为纯文本片段', () => {
  assert.equal(typeof homeUtils.splitHighlightFragments, 'function', '缺少纯文本高亮方法');

  const fragments = homeUtils.splitHighlightFragments('CPU <metric> usage', 'cpu <metric>');

  assert.deepEqual(fragments, [
    { text: 'CPU', highlight: true, start: 0 },
    { text: ' ', highlight: false, start: 3 },
    { text: '<metric>', highlight: true, start: 4 },
    { text: ' usage', highlight: false, start: 12 },
  ]);
});

test('搜索关键词中的正则特殊字符按原文匹配', () => {
  assert.equal(typeof homeUtils.splitHighlightFragments, 'function', '缺少纯文本高亮方法');

  const fragments = homeUtils.splitHighlightFragments('load[5m] load5m', 'load[5m]');

  assert.deepEqual(fragments, [
    { text: 'load[5m]', highlight: true, start: 0 },
    { text: ' load5m', highlight: false, start: 8 },
  ]);
});

test('策略描述提示使用纯文本并保留多行内容', () => {
  assert.equal(typeof strategyUtils.getItemDescriptionTooltip, 'function', '缺少策略描述提示配置');

  const tooltip = strategyUtils.getItemDescriptionTooltip([
    { val: 'sum(rate(metric[5m]))' },
    { val: '<metric data-kind="sample">cpu</metric>' },
  ]);

  assert.deepEqual(tooltip, {
    allowHTML: false,
    content: 'sum(rate(metric[5m]))\n<metric data-kind="sample">cpu</metric>',
    extCls: 'strategy-item-description-tooltips',
  });
});
