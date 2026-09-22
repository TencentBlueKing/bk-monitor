const { spawn, spawnSync } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');

const PKG_DIR = path.resolve(__dirname, '../apm-vue3-for-vue2');
const DIST_JS = path.resolve(PKG_DIR, 'dist/index.js');
const DIST_CSS = path.resolve(PKG_DIR, 'dist/index.css');
const LOCK_FILE = path.resolve(PKG_DIR, '.ensure.lock');
const WATCH_PID_FILE = path.resolve(PKG_DIR, '.watch.pid');
const WEBPACK_ROOT = path.resolve(__dirname, '..');
const LOCK_TIMEOUT_MS = 10 * 60 * 1000;
const LOCK_POLL_MS = 300;
/** Vue3 独立工程 / 移动端不会解析 monitor-ui 里的 Vue2 宿主容器，跳过以免白等一次 Vite */
const SKIP_APPS = new Set(['trace', 'mobile']);

const hasDist = () => fs.existsSync(DIST_JS) && fs.existsSync(DIST_CSS);

const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));

const isPidAlive = pid => {
  if (!pid) return false;
  try {
    process.kill(pid, 0);
    return true;
  } catch {
    return false;
  }
};

const readPidFile = file => {
  try {
    const raw = fs.readFileSync(file, 'utf8').trim();
    const pid = Number(raw);
    return Number.isInteger(pid) ? pid : 0;
  } catch {
    return 0;
  }
};

const isWatchAlive = () => isPidAlive(readPidFile(WATCH_PID_FILE));

const acquireLock = async () => {
  fs.mkdirSync(PKG_DIR, { recursive: true });
  const start = Date.now();
  while (true) {
    try {
      const fd = fs.openSync(LOCK_FILE, 'wx');
      fs.writeFileSync(fd, String(process.pid));
      fs.closeSync(fd);
      return;
    } catch (error) {
      if (error.code !== 'EEXIST') throw error;
    }
    if (!isPidAlive(readPidFile(LOCK_FILE))) {
      try {
        fs.unlinkSync(LOCK_FILE);
      } catch {
        /* 并发方可能已经删了 */
      }
      continue;
    }
    if (Date.now() - start > LOCK_TIMEOUT_MS) {
      throw new Error('[ensure] @blueking/apm-vue3-for-vue2 lock timeout');
    }
    await sleep(LOCK_POLL_MS);
  }
};

const releaseLock = () => {
  try {
    fs.unlinkSync(LOCK_FILE);
  } catch {
    /* ignore */
  }
};

const spawnPnpm = (script, { sync, envNodeEnv }) => {
  const options = {
    cwd: WEBPACK_ROOT,
    stdio: 'inherit',
    shell: process.platform === 'win32',
    env: { ...process.env, NODE_ENV: envNodeEnv },
  };
  if (sync) {
    return spawnSync('pnpm', ['run', script], options);
  }
  return spawn('pnpm', ['run', script], options);
};

const buildLib = () => {
  console.info('[ensure] building @blueking/apm-vue3-for-vue2 (production) …');
  const result = spawnPnpm('build:apm-vue3-for-vue2', { sync: true, envNodeEnv: 'production' });
  if (result.status !== 0) {
    throw new Error('[ensure] pnpm build:apm-vue3-for-vue2 failed');
  }
};

const waitForDist = async ({ hasExited } = {}) => {
  const start = Date.now();
  while (!hasDist()) {
    if (hasExited?.()) {
      throw new Error('[ensure] @blueking/apm-vue3-for-vue2 watch exited before dist was ready');
    }
    if (Date.now() - start > LOCK_TIMEOUT_MS) {
      throw new Error('[ensure] @blueking/apm-vue3-for-vue2 watch timeout waiting for dist');
    }
    await sleep(LOCK_POLL_MS);
  }
};

const startWatch = () => {
  console.info('[ensure] watching @blueking/apm-vue3-for-vue2 (development) …');
  const child = spawnPnpm('dev:apm-vue3-for-vue2', { sync: false, envNodeEnv: 'development' });
  let exited = false;
  child.once('exit', () => {
    exited = true;
  });
  child.once('error', error => {
    exited = true;
    console.error('[ensure] failed to start apm-vue3-for-vue2 watch', error);
  });
  return {
    hasExited: () => exited,
  };
};

const ensureProduction = async () => {
  if (hasDist()) return;
  await acquireLock();
  try {
    if (hasDist()) return;
    buildLib();
    if (!hasDist()) {
      throw new Error('[ensure] @blueking/apm-vue3-for-vue2 dist missing after build');
    }
  } finally {
    releaseLock();
  }
};

const ensureDevelopment = async () => {
  if (isWatchAlive()) {
    if (!hasDist()) await waitForDist();
    return;
  }
  await acquireLock();
  try {
    if (isWatchAlive()) {
      if (!hasDist()) await waitForDist();
      return;
    }
    const watcher = startWatch();
    await waitForDist(watcher);
  } finally {
    releaseLock();
  }
};

/**
 * Vue2 宿主启动时按宿主模式拉起本包：
 * - production：dist 不存在才一次性构建
 * - development：拉起（或复用）Vite watch，并等到首份 dist
 * 并行 webpack（pnpm build 的 run-p）靠文件锁串行，避免 emptyOutDir 互踩。
 */
const ensureApmVue3ForVue2 = async (app, production) => {
  if (SKIP_APPS.has(app)) return;
  if (production) {
    await ensureProduction();
    return;
  }
  await ensureDevelopment();
};

module.exports = { ensureApmVue3ForVue2 };
