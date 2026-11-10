const fs = require('fs');
const path = require('path');

const envFileKeys = new Map();

function readEnvAssignments(envFile) {
  if (!fs.existsSync(envFile)) return new Map();
  const assignments = new Map();
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
    assignments.set(key, value);
  }
  return assignments;
}

function loadLocalEnv(envFile = path.resolve(__dirname, '.env.local'), options = {}) {
  const refresh = options.refresh === true;
  const owned = envFileKeys.get(envFile) || new Set();
  const assignments = readEnvAssignments(envFile);
  for (const [key, value] of assignments) {
    // 首次加载不覆盖启动进程时已经存在的环境变量；文件后续变更以文件为准。
    if (!refresh && process.env[key] !== undefined && !owned.has(key)) continue;
    process.env[key] = value;
    owned.add(key);
  }
  if (refresh) {
    for (const key of owned) {
      if (!assignments.has(key)) {
        delete process.env[key];
        owned.delete(key);
      }
    }
  }
  envFileKeys.set(envFile, owned);
}

function reloadLocalEnv(envFile = path.resolve(__dirname, '.env.local')) {
  loadLocalEnv(envFile, { refresh: true });
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
  reloadLocalEnv,
  devProxyUrl,
  devHost,
  devUrl,
  allowedHosts,
};
