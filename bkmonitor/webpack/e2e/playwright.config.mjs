import { defineConfig, devices } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const runsRoot = path.resolve(__dirname, '../.e2e-runs');
const runDir = path.resolve(requiredEnv('BKMONITOR_E2E_RUN_DIR'));
const baseURL = requiredEnv('BKMONITOR_E2E_BASE_URL');
const viewport = parseViewport(process.env.BKMONITOR_E2E_VIEWPORT || '1440x900');
const relativeRunDir = path.relative(runsRoot, runDir);

if (!relativeRunDir || relativeRunDir.startsWith('..') || path.isAbsolute(relativeRunDir)) {
  throw new Error('BKMONITOR_E2E_RUN_DIR 必须指向仓库 .e2e-runs/ 下的某次运行目录。');
}

const storageState = process.env.BKMONITOR_E2E_STORAGE_STATE
  ? path.resolve(process.env.BKMONITOR_E2E_STORAGE_STATE)
  : undefined;
if (storageState && !fs.existsSync(storageState)) {
  throw new Error(`登录态文件不存在：${storageState}`);
}
if (storageState) {
  const relativeStorageState = path.relative(runDir, storageState);
  if (relativeStorageState.startsWith('..') || path.isAbsolute(relativeStorageState)) {
    throw new Error('登录态文件必须位于本次 .e2e-runs/<run-id>/ 目录内。');
  }
}

export default defineConfig({
  testDir: path.join(runDir, 'tests'),
  testMatch: '**/*.spec.mjs',
  outputDir: path.join(runDir, 'test-results'),
  snapshotPathTemplate: path.join(runDir, 'snapshots/{projectName}/{testFilePath}/{arg}{ext}'),
  respectGitIgnore: false,
  fullyParallel: false,
  forbidOnly: true,
  retries: 0,
  workers: 1,
  timeout: 45_000,
  expect: { timeout: 10_000 },
  reporter: [
    ['list'],
    ['html', { outputFolder: path.join(runDir, 'html-report'), open: 'never' }],
    ['json', { outputFile: path.join(runDir, 'results.json') }],
  ],
  use: {
    ...devices['Desktop Chrome'],
    baseURL,
    headless: process.env.BKMONITOR_E2E_HEADED !== 'true',
    viewport,
    storageState,
    ignoreHTTPSErrors: true,
    actionTimeout: 10_000,
    navigationTimeout: 30_000,
    trace: 'retain-on-failure',
    screenshot: 'on',
    video: 'on',
  },
  projects: [{ name: 'chromium' }],
});

function parseViewport(value) {
  const match = /^(\d+)x(\d+)$/.exec(value);
  if (!match) {
    throw new Error('视口必须使用 <width>x<height>，例如 1440x900。');
  }
  return { width: Number(match[1]), height: Number(match[2]) };
}

function requiredEnv(name) {
  const value = process.env[name];
  if (!value) {
    throw new Error(`缺少环境变量 ${name}，请由调用方传入本次运行目录与目标地址。`);
  }
  return value;
}
