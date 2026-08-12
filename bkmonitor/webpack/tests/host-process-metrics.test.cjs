const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');

process.env.TS_NODE_PROJECT = path.resolve(__dirname, '../src/trace/tsconfig.json');
process.env.TS_NODE_COMPILER_OPTIONS = JSON.stringify({
  esModuleInterop: true,
  module: 'commonjs',
  moduleResolution: 'node',
});
require('ts-node/register/transpile-only');

const dayjs = require('dayjs');
const {
  formatMemRss,
  formatPercent,
  formatProcessUptimeDetail,
  formatProcessSeriesAlias,
  formatUptime,
} = require('../src/trace/pages/host/utils/process.ts');

test('进程运行时长按后端返回的秒数展示', () => {
  assert.equal(formatUptime(0), '0 h');
  assert.equal(formatUptime(3600), '1 h');
  assert.equal(formatUptime(86400), '1 d');

  const observedAt = 1729682400;
  const startTime = dayjs.unix(observedAt).subtract(86400, 'second').format('YYYY-MM-DD HH:mm:ss');
  assert.equal(formatProcessUptimeDetail(86400, observedAt), `1d (${startTime})`);
});

test('进程指标区分缺失值与真实零值', () => {
  assert.deepEqual(formatPercent(null), { text: '--', value: null, width: 0 });
  assert.deepEqual(formatPercent(0), { text: '0.00%', value: 0, width: 0 });
  assert.deepEqual(formatPercent(0.1532), { text: '15.32%', value: 15.32, width: 15.32 });
  assert.equal(formatMemRss(null), '--');
  assert.equal(formatMemRss(0), '0 B');
});

test('进程详情沿用主机时间上下文并按进程名过滤', () => {
  const source = fs.readFileSync(
    path.resolve(__dirname, '../src/trace/pages/host/components/host-process/process-detail/process-detail.tsx'),
    'utf8'
  );

  assert.match(source, /display_name:\s*props\.process\.name/);
  assert.match(source, /timeRange:\s*hostTimeRange/);
  assert.match(source, /timezone:\s*hostTimezone/);
  assert.match(source, /formatProcessUptimeDetail\(process\.uptime,\s*timeRangeTimestamp\.value\.end_time\)/);
  assert.doesNotMatch(source, /\['now-1d',\s*'now'\]/);
});

test('进程图例仅在查询返回 PID 时追加实例标识', () => {
  assert.equal(formatProcessSeriesAlias({ display_name: 'nginx' }, 'fallback'), 'nginx');
  assert.equal(formatProcessSeriesAlias({ display_name: 'nginx', pid: 123 }, 'fallback'), 'nginx|123');
  assert.equal(formatProcessSeriesAlias(undefined, 'fallback'), 'fallback');
});
