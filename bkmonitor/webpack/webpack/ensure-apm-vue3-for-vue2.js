const { spawnSync } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');

const PKG_DIR = path.resolve(__dirname, '../apm-vue3-for-vue2');
const DIST_JS = path.resolve(PKG_DIR, 'dist/index.js');
const DIST_CSS = path.resolve(PKG_DIR, 'dist/index.css');
const LOCK_FILE = path.resolve(PKG_DIR, '.ensure.lock');
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

const readLockPid = () => {
  try {
    const raw = fs.readFileSync(LOCK_FILE, 'utf8').trim();
    const pid = Number(raw);
    return Number.isInteger(pid) ? pid : 0;
  } catch {
    return 0;
  }
};

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
      if (!isPidAlive(readLockPid())) {
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
  }
};

const releaseLock = () => {
  try {
    fs.unlinkSync(LOCK_FILE);
  } catch {
    /* ignore */
  }
};

const buildLib = () => {
  console.info('[ensure] building @blueking/apm-vue3-for-vue2 …');
  const result = spawnSync('pnpm', ['run', 'build:apm-vue3-for-vue2'], {
    cwd: WEBPACK_ROOT,
    stdio: 'inherit',
    shell: process.platform === 'win32',
  });
  if (result.status !== 0) {
    throw new Error('[ensure] pnpm build:apm-vue3-for-vue2 failed');
  }
};

/**
 * Vue2 宿主启动时：本地 workspace 包的 dist 不存在才构建一次，之后跳过（dev / build 相同）。
 * 并行 webpack（pnpm build 的 run-p）靠文件锁串行，避免 emptyOutDir 互踩。
 */
const ensureApmVue3ForVue2 = async app => {
  if (SKIP_APPS.has(app)) return;
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

module.exports = { ensureApmVue3ForVue2 };
