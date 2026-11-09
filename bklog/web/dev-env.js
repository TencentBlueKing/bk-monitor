const fs = require('fs');
const path = require('path');

function loadLocalEnv(envFile = path.resolve(__dirname, '.env.local')) {
  if (!fs.existsSync(envFile)) return;
  const text = fs.readFileSync(envFile, 'utf8');
  for (const line of text.split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('#')) continue;
    const eq = trimmed.indexOf('=');
    if (eq <= 0) continue;
    const key = trimmed.slice(0, eq).trim();
    if (!/^[A-Za-z_][A-Za-z0-9_]*$/.test(key)) continue;
    let value = trimmed.slice(eq + 1).trim();
    if (
      (value.startsWith('"') && value.endsWith('"'))
      || (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1);
    }
    if (process.env[key] === undefined) process.env[key] = value;
  }
}

function devProxyUrl() {
  return process.env.BKLOG_DEV_PROXY_URL || 'http://127.0.0.1';
}

function devHost() {
  return process.env.BKLOG_DEV_HOST || 'localhost';
}

function devUrl(port = '4175') {
  return process.env.BKLOG_DEV_URL || `${devHost()}:${port}`;
}

function allowedHosts() {
  const fromList = String(process.env.BKLOG_DEV_ALLOWED_HOSTS || '')
    .split(',')
    .map(item => item.trim())
    .filter(Boolean);
  const host = String(process.env.BKLOG_DEV_HOST || '').trim();
  return Array.from(new Set([...fromList, ...(host ? [host] : []), 'localhost', '127.0.0.1']));
}

module.exports = {
  loadLocalEnv,
  devProxyUrl,
  devHost,
  devUrl,
  allowedHosts,
};
