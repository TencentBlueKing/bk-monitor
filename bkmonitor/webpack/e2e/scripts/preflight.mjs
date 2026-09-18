#!/usr/bin/env node

import { chromium } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const AUTH_PATH_RE =
  /(?:\/passport(?:\/|$)|\/signin(?:\/|$)|\/oauth(?:\/|$)|\/idps?(?:\/|$)|\/login(?:\/|$)|\/auth(?:\/|$))/i;
const AUTH_HOST_RE = /(?:^|\.)(?:login|passport|oauth|idp)(?:\.|$)/i;

async function firstVisible(page, selectors) {
  for (const selector of selectors) {
    try {
      if (await page.locator(selector).first().isVisible()) return selector;
    } catch {
      return `INVALID_SELECTOR:${selector}`;
    }
  }
  return '';
}

function help() {
  console.log(`Usage:
  pnpm e2e:preflight -- --run-dir <dir> --base-url <url>
  pnpm e2e:preflight -- --self-test

Checks server reachability, login redirects and the target route readiness without running business scenarios.`);
}

function isAuthRedirect(baseUrl, finalUrl, status) {
  if (status === 401) return true;
  const base = new URL(baseUrl);
  const final = new URL(finalUrl);
  return (
    AUTH_HOST_RE.test(final.hostname) ||
    (AUTH_PATH_RE.test(final.pathname) && (final.origin !== base.origin || final.pathname !== base.pathname))
  );
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  if (args.help) {
    help();
    return;
  }
  if (args.selfTest) {
    runSelfTest();
    return;
  }
  for (const name of ['run-dir', 'base-url']) {
    if (!args[name]) throw new Error(`--${name} is required.`);
  }

  const baseUrl = new URL(args['base-url']);
  if (!['http:', 'https:'].includes(baseUrl.protocol)) throw new Error('--base-url must use http or https.');

  const scriptDir = path.dirname(fileURLToPath(import.meta.url));
  const repoRoot = path.resolve(scriptDir, '../..');
  const runDir = resolveRunDir(repoRoot, args['run-dir']);
  const scopePath = path.join(runDir, 'scope.json');
  if (!fs.existsSync(scopePath)) throw new Error('scope.json was not found. Create the run with pnpm e2e:init first.');

  const scope = JSON.parse(fs.readFileSync(scopePath, 'utf8'));
  const runtime = scope.runtime || {};
  const entryPath = String(runtime.entryPath || '');
  const readySelector = String(runtime.readySelector || '');
  const blockedSelectors = Array.isArray(runtime.blockedSelectors)
    ? runtime.blockedSelectors.map(String).filter(Boolean)
    : [];
  const targetUrl = new URL(entryPath || '/', baseUrl);
  const result = {
    status: 'UNCLASSIFIED',
    checkedAt: new Date().toISOString(),
    baseOrigin: baseUrl.origin,
    finalOrigin: '',
    httpStatus: null,
    blockedSelector: '',
    readySelector,
    evidence: '',
  };

  if (!entryPath || !readySelector) {
    result.status = 'ROUTE_NOT_CONFIGURED';
    await writeResult(runDir, result);
    process.exitCode = 2;
    return;
  }

  let browser;
  let page;
  try {
    browser = await chromium.launch({ headless: true });
    const context = await browser.newContext({ ignoreHTTPSErrors: true });
    page = await context.newPage();
    const response = await page.goto(targetUrl.toString(), { waitUntil: 'domcontentloaded', timeout: 30_000 });
    const finalUrl = page.url();
    result.finalOrigin = new URL(finalUrl).origin;
    result.httpStatus = response?.status() ?? null;

    if (isAuthRedirect(targetUrl.toString(), finalUrl, result.httpStatus)) {
      result.status = 'AUTH_REQUIRED';
    } else if (result.httpStatus === 403) {
      result.status = 'HTTP_FORBIDDEN';
    } else if (result.httpStatus && result.httpStatus >= 400) {
      result.status = 'HTTP_ERROR';
    } else {
      const blockedSelector = await firstVisible(page, blockedSelectors);
      if (blockedSelector) {
        result.status = blockedSelector.startsWith('INVALID_SELECTOR:') ? 'PREFLIGHT_INVALID' : 'ROUTE_BLOCKED';
        result.blockedSelector = blockedSelector;
      } else {
        try {
          await page.locator(readySelector).first().waitFor({ state: 'visible', timeout: 10_000 });
          result.status = 'READY';
        } catch {
          const lateUrl = page.url();
          result.finalOrigin = new URL(lateUrl).origin;
          const lateBlockedSelector = await firstVisible(page, blockedSelectors);
          if (isAuthRedirect(targetUrl.toString(), lateUrl, result.httpStatus)) {
            result.status = 'AUTH_REQUIRED';
          } else if (lateBlockedSelector) {
            result.status = lateBlockedSelector.startsWith('INVALID_SELECTOR:') ? 'PREFLIGHT_INVALID' : 'ROUTE_BLOCKED';
            result.blockedSelector = lateBlockedSelector;
          } else {
            result.status = 'ROUTE_NOT_READY';
          }
        }
      }
    }
  } catch {
    result.status = 'SERVER_UNREACHABLE';
  }

  await writeResult(runDir, result, page);
  await browser?.close();
  process.exitCode = result.status === 'READY' ? 0 : 2;
}

function parseArgs(argv) {
  const args = {};
  for (let index = 0; index < argv.length; index += 1) {
    const token = argv[index];
    if (token === '--') continue;
    if (token === '--help' || token === '-h') {
      args.help = true;
      continue;
    }
    if (token === '--self-test') {
      args.selfTest = true;
      continue;
    }
    if (!token.startsWith('--')) throw new Error(`Unexpected argument: ${token}`);
    const value = argv[index + 1];
    if (!value || value.startsWith('--')) throw new Error(`Missing value for ${token}`);
    args[token.slice(2)] = value;
    index += 1;
  }
  return args;
}

function resolveRunDir(repoRoot, value) {
  const runsRoot = path.join(repoRoot, '.e2e-runs');
  const runDir = path.resolve(repoRoot, value);
  const relative = path.relative(runsRoot, runDir);
  if (!relative || relative.startsWith('..') || path.isAbsolute(relative)) {
    throw new Error('--run-dir must point to a child directory of .e2e-runs/.');
  }
  return runDir;
}

function runSelfTest() {
  const cases = [
    ['https://appdev.example.test/', 'https://passport.example.test/login/', 200, true],
    ['https://appdev.example.test/', 'https://login.example.test/', 200, true],
    ['https://appdev.example.test/', 'https://appdev.example.test/login/', 200, true],
    ['https://appdev.example.test/', 'https://appdev.example.test/auth-settings/', 200, false],
    ['https://appdev.example.test/', 'https://appdev.example.test/page/', 401, true],
    ['https://appdev.example.test/', 'https://appdev.example.test/page/', 200, false],
  ];
  for (const [baseUrl, finalUrl, status, expected] of cases) {
    const actual = isAuthRedirect(baseUrl, finalUrl, status);
    if (actual !== expected) throw new Error(`self-test failed for ${finalUrl}`);
  }
  console.log('SELF_TEST_PASS');
}

async function writeResult(runDir, result, page) {
  if (result.status !== 'READY' && page) {
    try {
      await page.screenshot({ path: path.join(runDir, 'preflight.png'), fullPage: false });
      result.evidence = 'preflight.png';
    } catch {
      result.evidence = '';
    }
  }
  const resultPath = path.join(runDir, 'preflight.json');
  fs.writeFileSync(resultPath, `${JSON.stringify(result, null, 2)}\n`, 'utf8');
  console.log(JSON.stringify({ status: result.status, resultPath }, null, 2));
}

main().catch(error => {
  console.error(error.message);
  process.exitCode = 1;
});
