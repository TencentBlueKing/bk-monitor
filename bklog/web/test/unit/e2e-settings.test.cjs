const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { test } = require('node:test');
const root = path.resolve(__dirname, '../..');
const source = fs.readFileSync(path.join(root, 'local.settings.e2e.aafe.cjs'), 'utf8');
function load(url = 'http://127.0.0.1:41001') {
  const context = { module: { exports: {} }, __dirname: root, URL,
    process: { env: { AAFE_E2E_DEV_URL: url } },
    require(name) {
      if (name === 'node:fs') return { readFileSync: () => JSON.stringify({ e2e: { devServer: {
        url: 'http://127.0.0.1:8011', proxyTarget: 'https://example.test', proxyPaths: ['/api', '/rest'],
      } } }) };
      return require(name);
    },
  };
  vm.runInNewContext(source, context);
  return context.module.exports;
}
test('task URL overrides default port and preserves proxy paths', () => {
  const settings = load();
  assert.equal(settings.port, 41001);
  assert.equal(settings.host, '127.0.0.1');
  assert.deepEqual(JSON.parse(JSON.stringify(settings.proxy[0].context)), ['/api', '/rest']);
});
test('proxy forwards browser cookie and removes stale cookie when absent', () => {
  const headers = new Map([['Cookie', 'stale-fixture']]);
  const req = { setHeader: (k, v) => headers.set(k, v), removeHeader: k => headers.delete(k) };
  const proxy = load().proxy[0];
  proxy.onProxyReq(req, { headers: { cookie: 'test-fixture=1' } });
  assert.equal(headers.get('Cookie'), 'test-fixture=1');
  proxy.onProxyReq(req, { headers: {} });
  assert.equal(headers.has('Cookie'), false);
});
test('rejects nonlocal dev URL', () => {
  assert.throws(() => load('https://example.test'), /local HTTP/);
});
