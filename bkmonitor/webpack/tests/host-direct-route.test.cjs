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

const { parseBizId } = require('../src/monitor-common/utils/index.ts');
const { buildHostAppUrl } = require('../src/monitor-pc/pages/host/host-url.ts');
const hostSource = fs.readFileSync(path.resolve(__dirname, '../src/monitor-pc/pages/host/host.tsx'), 'utf8');

test('主机微应用地址保留外层主机 ID 与进程查询参数', () => {
  const url = buildHostAppUrl(
    'https://bkmonitor.example.com/trace/',
    2,
    '/trace/host/92749?activeTab=process&hostProcessName=kubelet'
  );

  assert.equal(
    url,
    'https://bkmonitor.example.com/trace/?bizId=2#/trace/host/92749?activeTab=process&hostProcessName=kubelet'
  );
});

test('未提供外层路径时保持主机首页默认地址', () => {
  assert.equal(buildHostAppUrl('http://localhost:7002/', 2, ''), 'http://localhost:7002/?bizId=2#/trace/host');
});

test('主机外层组件将当前完整路由传给微应用地址', () => {
  assert.match(hostSource, /buildHostAppUrl\(baseUrl, this\.\$store\.getters\.bizId, this\.\$route\.fullPath\)/);
});

test('旧链接 ?bizId=x/#/ 经 URLSearchParams 得到 2/，parseBizId 仍解析为 2', () => {
  const href = 'https://bkmonitor.example.com/?bizId=2/#/strategy-config/edit/9668';
  const raw = new URL(href).searchParams.get('bizId');
  assert.equal(raw, '2/');
  assert.equal(Number.isNaN(Number(raw)), true);
  assert.equal(parseBizId(raw), 2);
});

test('非数字业务 ID 不能写入全局状态', () => {
  assert.equal(Number.isFinite(parseBizId('abc')), false);
  assert.equal(Number.isFinite(parseBizId(Number.NaN)), false);
});
