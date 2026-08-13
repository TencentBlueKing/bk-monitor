const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');

process.env.TS_NODE_PROJECT = path.resolve(__dirname, '../src/monitor-pc/tsconfig.json');
process.env.TS_NODE_COMPILER_OPTIONS = JSON.stringify({
  module: 'commonjs',
  moduleResolution: 'node',
});
global.window = {
  i18n: {
    t: value => value,
  },
};
require('ts-node/register/transpile-only');

const { ProcessDetailTabEnum } = require('../src/trace/pages/host/constants/enum.ts');
const { PROCESS_DETAIL_TABS } = require('../src/trace/pages/host/constants/process.ts');
const processDetailSource = fs.readFileSync(
  path.resolve(__dirname, '../src/trace/pages/host/components/host-process/process-detail/process-detail.tsx'),
  'utf8'
);

test('进程详情普通入口只展示本期已交付的指标视图', () => {
  assert.deepEqual(
    PROCESS_DETAIL_TABS.map(tab => ({ id: tab.id, label: tab.label, icon: tab.icon })),
    [{ id: ProcessDetailTabEnum.METRIC, label: '指标视图', icon: 'icon-zhibiaojiansuo' }]
  );
});

test('进程详情深链不能注入未注册的 Profiling 标签', () => {
  assert.match(processDetailSource, /PROCESS_DETAIL_TABS\.map\(tab =>/);
  assert.match(processDetailSource, /shallowRef<ProcessDetailTabType>\(ProcessDetailTabEnum\.METRIC\)/);
  assert.doesNotMatch(processDetailSource, /(?:useRoute|\$route|route\.query)/);
  assert.equal(
    PROCESS_DETAIL_TABS.some(tab => tab.id === ProcessDetailTabEnum.PROFILING),
    false
  );
});
