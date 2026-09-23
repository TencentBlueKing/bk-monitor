#!/usr/bin/env node

import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import { createRequire } from 'node:module';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(scriptDir, '../..');
const require = createRequire(import.meta.url);
const checks = [];

function check(name, operation, fix) {
  try {
    const detail = operation();
    checks.push({ name, ok: true, detail });
  } catch (error) {
    checks.push({ name, ok: false, detail: error.message, fix });
  }
}

check(
  'Node.js >= 20.17.0',
  () => {
    const [major, minor] = process.versions.node.split('.').map(Number);
    if (major < 20 || (major === 20 && minor < 17)) {
      throw new Error(`当前版本 ${process.versions.node}`);
    }
    return process.versions.node;
  },
  '切换到项目要求的 Node.js 版本。'
);

for (const dependency of ['@playwright/test', 'pixelmatch', 'pngjs']) {
  check(`依赖 ${dependency}`, () => require.resolve(dependency), '执行 pnpm install。');
}

check(
  'Playwright Chromium',
  () => {
    const { chromium } = require('@playwright/test');
    const executablePath = chromium.executablePath();
    if (!fs.existsSync(executablePath)) {
      throw new Error('浏览器二进制尚未安装');
    }
    return executablePath;
  },
  '执行 pnpm e2e:install。'
);

check(
  '.e2e-runs 已被 Git 忽略',
  () => {
    execFileSync('git', ['check-ignore', '-q', '.e2e-runs/probe'], { cwd: repoRoot });
    return '.e2e-runs/';
  },
  '检查仓库根目录 .gitignore。'
);

for (const item of checks) {
  console.log(`${item.ok ? 'PASS' : 'FAIL'}  ${item.name}${item.ok ? ` — ${item.detail}` : ` — ${item.detail}`}`);
  if (!item.ok) {
    console.log(`      修复：${item.fix}`);
  }
}

const failed = checks.filter(item => !item.ok).length;
console.log(`\n${checks.length - failed}/${checks.length} 项检查通过。`);
process.exit(failed === 0 ? 0 : 1);
