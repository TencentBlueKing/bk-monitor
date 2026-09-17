#!/usr/bin/env node

import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import { createRequire } from 'node:module';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

function help() {
  console.log(`Usage:
  pnpm e2e:run -- --run-dir <dir> --base-url <url> [--storage-state <file>] [--headed]

Runs only the one-off specs inside the selected .e2e-runs directory.`);
}

function parseArgs(argv) {
  const args = {};
  for (let index = 0; index < argv.length; index += 1) {
    const token = argv[index];
    if (token === '--') {
      continue;
    }
    if (token === '--help' || token === '-h') {
      args.help = true;
      continue;
    }
    if (token === '--headed') {
      args.headed = true;
      continue;
    }
    if (!token.startsWith('--')) {
      throw new Error(`Unexpected argument: ${token}`);
    }
    const value = argv[index + 1];
    if (!value || value.startsWith('--')) {
      throw new Error(`Missing value for ${token}`);
    }
    args[token.slice(2)] = value;
    index += 1;
  }
  return args;
}

const args = parseArgs(process.argv.slice(2));
if (args.help) {
  help();
  process.exit(0);
}
for (const name of ['run-dir', 'base-url']) {
  if (!args[name]) {
    throw new Error(`--${name} is required.`);
  }
}

const url = new URL(args['base-url']);
if (!['http:', 'https:'].includes(url.protocol)) {
  throw new Error('--base-url must use http or https.');
}

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(scriptDir, '../..');
const runsRoot = path.join(repoRoot, '.e2e-runs');
const runDir = path.resolve(repoRoot, args['run-dir']);
const relativeRunDir = path.relative(runsRoot, runDir);
if (!relativeRunDir || relativeRunDir.startsWith('..') || path.isAbsolute(relativeRunDir)) {
  throw new Error('--run-dir must point to a child directory of .e2e-runs/.');
}
if (!fs.existsSync(path.join(runDir, 'scope.json')) || !fs.existsSync(path.join(runDir, 'tests'))) {
  throw new Error('The run directory is incomplete. Create it with pnpm e2e:init first.');
}

const scope = JSON.parse(fs.readFileSync(path.join(runDir, 'scope.json'), 'utf8'));
const viewport = scope.environment?.viewport || '1440x900';
const require = createRequire(import.meta.url);
const playwrightCli = require.resolve('@playwright/test/cli');
const configPath = path.join(repoRoot, 'e2e/playwright.config.mjs');
const env = {
  ...process.env,
  BKMONITOR_E2E_RUN_DIR: runDir,
  BKMONITOR_E2E_BASE_URL: url.toString(),
  BKMONITOR_E2E_VIEWPORT: viewport,
  BKMONITOR_E2E_HEADED: args.headed ? 'true' : 'false',
};
if (args['storage-state']) {
  const storageState = path.resolve(repoRoot, args['storage-state']);
  const relativeStorageState = path.relative(runDir, storageState);
  if (relativeStorageState.startsWith('..') || path.isAbsolute(relativeStorageState)) {
    throw new Error('--storage-state must point to a file inside the selected run directory.');
  }
  env.BKMONITOR_E2E_STORAGE_STATE = storageState;
}

const result = spawnSync(process.execPath, [playwrightCli, 'test', '--config', configPath], {
  cwd: repoRoot,
  env,
  stdio: 'inherit',
});

if (result.error) {
  throw result.error;
}
console.log(`HTML report: ${path.join(runDir, 'html-report/index.html')}`);
console.log(`JSON results: ${path.join(runDir, 'results.json')}`);
process.exit(result.status ?? 1);
