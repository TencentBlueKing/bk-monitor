/**
 * Vite CLI 不认识 `-a`，会当成 unknown option 直接退出。
 * 这里用 Vite 的 Node API 跑构建，让 `process.argv` 里的 `-a` / `--analyze`
 * 能被 create-config.ts 读到（与主站 bkmonitor-cli build -a 对齐）。
 *
 * 模式与宿主一致：优先用 NODE_ENV（ensure / bkmonitor-cli 会注入），
 * 独立跑脚本时 --watch → development，否则 production。
 *
 * 用法：
 *   production：node ./scripts/vue3-lib/vite-build.mjs ./scripts/build.apm-vue3-for-vue2.ts [-a]
 *   watch：     node ./scripts/vue3-lib/vite-build.mjs ./scripts/build.apm-vue3-for-vue2.ts --watch
 */
import { unlinkSync, writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { build } from 'vite';

const args = process.argv.slice(2);
const watch = args.includes('--watch') || args.includes('-w');
const configArg = args.find(arg => arg !== '-a' && arg !== '--analyze' && !arg.startsWith('-'));
const envMode = process.env.NODE_ENV;
const mode =
  envMode === 'production' || envMode === 'development'
    ? envMode
    : watch
      ? 'development'
      : 'production';

if (!configArg) {
  console.error(
    'usage: node ./scripts/vue3-lib/vite-build.mjs <vite-config> [--watch|-w] [-a|--analyze]'
  );
  process.exit(1);
}

const isApmVue3Watch = watch && /build\.apm-vue3-for-vue2/.test(configArg);
const watchPidFile = isApmVue3Watch
  ? resolve(dirname(fileURLToPath(import.meta.url)), '../../apm-vue3-for-vue2/.watch.pid')
  : '';

const cleanupWatchPid = () => {
  if (!watchPidFile) return;
  try {
    unlinkSync(watchPidFile);
  } catch {
    /* ignore */
  }
};

if (watchPidFile) {
  writeFileSync(watchPidFile, String(process.pid));
  process.once('exit', cleanupWatchPid);
}

try {
  const result = await build({
    configFile: resolve(configArg),
    mode,
    ...(watch ? { build: { watch: {}, emptyOutDir: false } } : {}),
  });
  if (watch && result && typeof result.close === 'function') {
    const shutdown = async () => {
      await result.close();
      cleanupWatchPid();
      process.exit(0);
    };
    process.once('SIGINT', shutdown);
    process.once('SIGTERM', shutdown);
  }
} catch (error) {
  cleanupWatchPid();
  console.error(error);
  process.exit(1);
}
