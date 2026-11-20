/* Copyright (C) 2021 THL A29 Limited, a Tencent company, MIT License. */
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
const packageRoot = fileURLToPath(new URL('../packages/web-v3/', import.meta.url));
const manager = JSON.parse(readFileSync(resolve(packageRoot, 'package.json'), 'utf8')).packageManager;
// Install only the locked Vue3 package; never install the root/V2 dependency tree.
for (const args of [
  ['--ignore-workspace', 'install', '--frozen-lockfile', '--prod=false'],
  ['--ignore-workspace', 'run', 'build'],
]) {
  const env = args.includes('build') ? { ...process.env, NODE_ENV: 'production' } : process.env;
  let result = spawnSync(process.env.PNPM || 'pnpm', args, { cwd: packageRoot, env, stdio: 'inherit' });
  // Existing build hosts may only have Node/npm. Bootstrap the pinned pnpm via npm.
  if (!process.env.PNPM && result.error?.code === 'ENOENT') {
    result = spawnSync('npm', ['--loglevel=error', 'exec', '--yes', '--package', manager, '--', 'pnpm', ...args], { cwd: packageRoot, env, stdio: 'inherit' });
  }
  if (result.error) { console.error(result.error.message); process.exit(1); }
  if (result.status !== 0) process.exit(result.status || 1);
}
