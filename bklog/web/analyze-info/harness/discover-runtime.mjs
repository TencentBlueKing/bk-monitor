/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台 (BlueKing PaaS):
 *
 * ---------------------------------------------------
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
 * documentation files (the "Software"), to deal in the Software without restriction, including without limitation
 * the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
 * to permit persons to whom the Software is furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all copies or substantial portions of
 * the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
 * THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
 * CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
 * IN THE SOFTWARE.
 */

/** Discovery run: denied dependencies are NOT a product failure or a baseline. */
import { createRequire } from 'node:module';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { resolve } from 'node:path';
const require = createRequire(new URL('../../packages/web-v3/package.json', import.meta.url));
const {chromium} = require('@playwright/test');
const target = process.argv[2];
if (!target || new URL(target).hostname !== 'appdev.woa.com') throw new Error('Use verified appdev.woa.com dev target');
const out = fileURLToPath(new URL('../runs/discovery/', import.meta.url));
mkdirSync(out, {recursive: true});
const {classifyResponse} = await import('./response-classifier.mjs');
const requests = [], errors = [], responses = [];
const {requestPolicy} = await import('./protocol.mjs');
const policy = JSON.parse(readFileSync(new URL('../spec/read-policy.json', import.meta.url), 'utf8'));
for (const rule of policy.rules) {
  const {createHash} = await import('node:crypto');
  const bytes = readFileSync(new URL('../../packages/web-v2/src/' + rule.source.file, import.meta.url));
  if (createHash('sha256').update(bytes).digest('hex') !== rule.source.sha256) throw new Error('POLICY_SOURCE_CHANGED');
}
const browser = await chromium.launch({headless: true, executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
let authBlocked = false;
try {
  const context = await browser.newContext({viewport: {width: 1440, height: 900}, timezoneId: 'Asia/Shanghai', locale: 'zh-CN', serviceWorkers: 'block'});
  await context.route('**/*', async route => {
    const request = route.request();
    const url = new URL(request.url());
    if (url.origin !== new URL(target).origin || /login|oauth|authenticate/i.test(url.pathname)) {
      if (request.isNavigationRequest()) authBlocked = true;
      await route.abort('blockedbyclient');
      return;
    }
    if (['xhr', 'fetch'].includes(request.resourceType())) {
      let bodyKeys = [];
      try {bodyKeys = Object.keys(request.postDataJSON() ?? {});} catch {}
      const decision = requestPolicy({url: request.url(), method: request.method()}, policy.rules);
      const excluded = policy.rules.find(r => r.path === url.pathname && r.method === request.method() && r.semantics === 'TELEMETRY');
      if (excluded && decision.reason === 'WRITE_NOT_AUTHORIZED') decision.reason = 'EXCLUDED_TELEMETRY';
      requests.push({method: request.method(), path: url.pathname, queryKeys: [...url.searchParams.keys()], bodyKeys, ...decision});
      if (decision.decision === 'ALLOW') await route.continue();
      else await route.abort('blockedbyclient');
      return;
    }
    await route.continue();
  });
  const page = await context.newPage();
  page.on('response', async response => {
    if (!['xhr', 'fetch'].includes(response.request().resourceType())) return;
    const contentType = response.headers()['content-type'] ?? '';
    const classification = classifyResponse({status: response.status(), headers: response.headers()});
    if (classification === 'AUTH_BLOCKED') authBlocked = true;
    responses.push({path: new URL(response.url()).pathname, status: response.status(), contentType, classification});
  });
  page.on('pageerror', error => errors.push(error.message.replace(/https?:[^ ]+/g, '<url>').slice(0, 300)));
  const response = await page.goto(target, {waitUntil: 'domcontentloaded', timeout: 60000});
  // Wait for the bootstrap endpoint to be discovered, not for business acceptance.
  const started = Date.now();
  while (!requests.some(r => r.decision === 'BLOCK' && r.reason === 'UNCLASSIFIED_ENDPOINT') && !authBlocked && Date.now() - started < 15000) await new Promise(resolve => setTimeout(resolve, 200));
  await page.screenshot({path: resolve(out, `discovery-${Date.now()}.png`)});
  const result = {schemaVersion: 1, scope: 'POLICY_DISCOVERY_NOT_BASELINE', status: authBlocked ? 'AUTH_BLOCKED' : 'NEEDS_ENDPOINT_REVIEW', documentStatus: response?.status(), route: new URL(page.url()).hash.split('?')[0], requests, responses, errors};
  writeFileSync(resolve(out, `bootstrap-${Date.now()}.json`), JSON.stringify(result, null, 2) + '\n');
  console.log(JSON.stringify({status: result.status, requests: requests.length, pendingReview: requests.filter(r => r.reason === 'UNCLASSIFIED_ENDPOINT'), nonSuccessResponses: responses.filter(r => r.status >= 400), errors}));
} finally {await browser.close();}
