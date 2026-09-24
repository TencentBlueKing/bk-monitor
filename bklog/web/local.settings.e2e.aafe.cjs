// Project-owned AAFE E2E settings. Never reads .cookie or local.settings.js.
const fs = require('node:fs');
const path = require('node:path');
const root = process.env.AAFE_E2E_CONFIG_ROOT || __dirname;
const config = JSON.parse(fs.readFileSync(path.join(root, '.aafe.config.json'), 'utf8')).e2e?.devServer || {};
const url = new URL(process.env.AAFE_E2E_DEV_URL || config.url);
if (!['127.0.0.1', 'localhost', '[::1]'].includes(url.hostname) || url.protocol !== 'http:') throw new Error('E2E dev URL must be local HTTP');
const target = new URL(config.proxyTarget);
if (!['http:', 'https:'].includes(target.protocol) || target.username || target.password) throw new Error('Invalid E2E proxy target');
function inheritRequestCookie(proxyReq, req) {
  if (req.headers.cookie) proxyReq.setHeader('Cookie', req.headers.cookie);
  else proxyReq.removeHeader('Cookie');
}
const proxy = {
  context: config.proxyPaths || ['/api'], target: target.href,
  changeOrigin: true, secure: config.secure !== false,
  onProxyReq: inheritRequestCookie
};
module.exports = {
  host: url.hostname === 'localhost' ? '127.0.0.1' : url.hostname.replace(/[\[\]]/g, ''),
  port: Number(url.port || 80), devProxyUrl: target.href,
  loginHost: new URL('/login', target).href, proxy: [proxy]
};
