#!/usr/bin/env node

import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

function help() {
  console.log(`Usage:
  pnpm e2e:init -- --title <text> [--viewport <width>x<height>]

Creates an ignored, repository-local run directory under .e2e-runs/.`);
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

function parseViewport(value) {
  const match = /^(\d+)x(\d+)$/.exec(value || '1440x900');
  if (!match) {
    throw new Error('Viewport must use <width>x<height>, for example 1440x900.');
  }
  const width = Number(match[1]);
  const height = Number(match[2]);
  if (width < 320 || height < 320) {
    throw new Error('Viewport is unexpectedly small.');
  }
  return { width, height };
}

function slugify(value) {
  const slug = value
    .normalize('NFKD')
    .replace(/[^a-zA-Z0-9]+/g, '-')
    .replace(/^-|-$/g, '')
    .toLowerCase()
    .slice(0, 36);
  return slug || 'scoped-e2e';
}

const args = parseArgs(process.argv.slice(2));
if (args.help) {
  help();
  process.exit(0);
}

const title = args.title || 'bkmonitor scoped E2E';
const viewport = parseViewport(args.viewport);
const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(scriptDir, '../..');
const runsRoot = path.join(repoRoot, '.e2e-runs');
const timestamp = new Date()
  .toISOString()
  .replace(/[-:]/g, '')
  .replace(/\.\d{3}Z$/, 'Z');
const runId = `${timestamp}-${slugify(title)}-${crypto.randomBytes(3).toString('hex')}`;
const runDir = path.join(runsRoot, runId);
const testsDir = path.join(runDir, 'tests');
const templatePath = path.join(repoRoot, 'e2e/templates/scoped-e2e.spec.mjs');

fs.mkdirSync(testsDir, { recursive: true });
fs.copyFileSync(templatePath, path.join(testsDir, 'scoped-e2e.spec.mjs'));

const scope = {
  runId,
  title,
  testPhase: 'reconnaissance',
  requirement: '',
  acceptanceCriteria: [],
  changedFiles: [],
  scopeBasis: [],
  changedArea: '',
  entry: '',
  runtime: {
    entryPath: '',
    readySelector: '',
    blockedSelectors: [],
  },
  environment: {
    app: '',
    mode: '',
    browser: 'Chromium',
    viewport: `${viewport.width}x${viewport.height}`,
  },
  publicSummary: {
    scope: '',
    environment: '',
    scenarios: [],
    checks: [],
    repair: '',
    visual: '',
    risks: [],
    uncovered: [],
  },
  classification: 'UNCLASSIFIED',
  scenarioDetails: [],
  repairHistory: [],
  risks: [],
  uncovered: [],
  visual: {
    mode: 'not-applicable',
    checked: false,
    classification: 'NOT_RUN',
    diffRatio: null,
    summary: '无视觉验收写不适用；设计还原或布局回归任务执行后补充。',
    masks: [],
    regions: [],
    evidence: [],
  },
  notes: [],
};

const scopePath = path.join(runDir, 'scope.json');
fs.writeFileSync(scopePath, `${JSON.stringify(scope, null, 2)}\n`, 'utf8');

const delivery = {
  public: {
    background: [],
    changes: [],
    behavior: { before: '', after: '' },
    reviewFocus: [],
    impact: [],
  },
  internal: {
    branch: '',
    commit: '',
    remoteBranch: '',
    prUrl: '',
    head: '',
    base: '',
    changes: [],
    impact: [],
    attachments: [],
  },
};
const deliveryPath = path.join(runDir, 'delivery.json');
fs.writeFileSync(deliveryPath, `${JSON.stringify(delivery, null, 2)}\n`, 'utf8');

console.log(
  JSON.stringify(
    {
      runId,
      runDir,
      specPath: path.join(testsDir, 'scoped-e2e.spec.mjs'),
      scopePath,
      deliveryPath,
      resultsPath: path.join(runDir, 'results.json'),
      preflightPath: path.join(runDir, 'preflight.json'),
      htmlReportPath: path.join(runDir, 'html-report', 'index.html'),
    },
    null,
    2
  )
);
