/**
 * Vite CLI 不认识 `-a`，会当成 unknown option 直接退出。
 * 这里用 Vite 的 Node API 跑构建，让 `process.argv` 里的 `-a` / `--analyze`
 * 能被 create-config.ts 读到（与主站 bkmonitor-cli build -a 对齐）。
 *
 * 用法：node ./scripts/vue3-lib/vite-build.mjs ./scripts/build.apm-vue3-for-vue2.ts [-a]
 */
import { resolve } from 'node:path';
import { build } from 'vite';

const args = process.argv.slice(2);
const configArg = args.find(arg => arg !== '-a' && arg !== '--analyze' && !arg.startsWith('-'));

if (!configArg) {
  console.error('usage: node ./scripts/vue3-lib/vite-build.mjs <vite-config> [-a|--analyze]');
  process.exit(1);
}

try {
  await build({ configFile: resolve(configArg) });
} catch (error) {
  console.error(error);
  process.exit(1);
}
