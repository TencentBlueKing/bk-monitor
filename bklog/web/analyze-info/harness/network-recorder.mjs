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

import {mkdirSync, writeFileSync} from 'node:fs';
import {resolve} from 'node:path';
import {createHash} from 'node:crypto';
import {requestPolicy, requestSignature, parseStream} from './protocol.mjs';
import {classifyResponse} from './response-classifier.mjs';
const hash = body => createHash('sha256').update(body).digest('hex');

/** Never serialize request headers/cookies. Full bodies stay in a private local directory. */
export async function installRecorder(context, {origin, rules, privateDir, businessContext, bodyFallback}) {
  mkdirSync(privateDir, {recursive: true, mode: 0o700});
  const entries = [], ids = new WeakMap(), pending = new Set();
  let observationPhase = 'bootstrap';
  const file = (name, body) => {
    writeFileSync(resolve(privateDir, name), body, {mode: 0o600});
    return {path: name, sha256: hash(body), bytes: Buffer.byteLength(body)};
  };
  const track = promise => {
    pending.add(promise);
    promise.finally(() => pending.delete(promise));
  };
  await context.route('**/*', async route => {
    const request = route.request(), url = new URL(request.url());
    if (url.origin !== origin || /(?:^|\/)(?:login|oauth)(?:\/|$)/i.test(url.pathname)) {
      await route.abort('blockedbyclient');
      return;
    }
    if (!['xhr', 'fetch', 'ping'].includes(request.resourceType()) && request.method() === 'GET' && !url.pathname.startsWith('/api/') && url.pathname !== '/notice/announcements/') {await route.continue(); return;}
    const policy = requestPolicy({method: request.method(), url: request.url()}, rules);
    const excluded = rules.find(r => r.path === url.pathname && r.method === request.method() && r.semantics === 'TELEMETRY');
    if (excluded && policy.reason === 'WRITE_NOT_AUTHORIZED') policy.reason = 'EXCLUDED_TELEMETRY';
    const id = `request-${entries.length + 1}`;
    const requestData = {url: request.url(), method: request.method(), body: request.postData(), context: businessContext};
    const entry = {
      id, path: url.pathname, method: request.method(), signature: requestSignature(requestData),
      observedDuring: observationPhase, causality: 'UNPROVEN_OBSERVATION_WINDOW',
      policy, startedAt: Date.now(), complete: false,
      request: file(`${id}.request.json`, Buffer.from(JSON.stringify(requestData))),
    };
    entries.push(entry);ids.set(request, entry);
    if (policy.decision === 'ALLOW') await route.continue();
    else await route.abort('blockedbyclient');
  });
  context.on('requestfinished', request => track((async () => {
    const entry = ids.get(request);if (!entry || entry.policy.decision !== 'ALLOW') return;
    try {
      const response = await request.response();
      let body;
      let transport = {source: 'PLAYWRIGHT_REQUEST_OBJECT'};
      try {body = await response.body();}
      catch (error) {
        if (!bodyFallback) throw error;
        const fallback = await bodyFallback(request);
        body = fallback.body;transport = fallback.transport;
      }
      const headers = response.headers();
      entry.response = {transport, status: response.status(), contentType: headers['content-type'] ?? '', classification: classifyResponse({status: response.status(), headers}), body: file(`${entry.id}.body`, body)};
      entry.finishedAt = Date.now();entry.complete = true;
      if (/ndjson/i.test(entry.response.contentType)) {
        const parsed = parseStream(body.toString('utf8'), {transportFinished: true, terminalRequired: true, terminal: chunk => chunk.value.event === 'done'});
        entry.stream = {events: parsed.chunks.length, errors: parsed.errors, terminalObserved: parsed.terminalObserved, complete: parsed.complete};
        entry.complete = parsed.complete;
      }
    } catch (error) {entry.captureError = error.message.slice(0, 180);}
  })()));
  context.on('requestfailed', request => {
    const entry = ids.get(request);if (!entry) return;
    entry.finishedAt = Date.now();entry.failure = request.failure()?.errorText;
    entry.cancelled = /abort|cancel/i.test(entry.failure ?? '');
  });
  return {
    entries,
    phase(id) {observationPhase = id;},
    async flush(timeoutMs = 30000) {
      const started = Date.now();
      while (entries.some(e => e.policy.decision === 'ALLOW' && !e.complete && !e.failure && !e.captureError) && Date.now() - started < timeoutMs) {
        await new Promise(resolve => setTimeout(resolve, 100));
      }
      await Promise.all([...pending]);
    },
    save(name = 'capture.json', metadata = {}) {return file(name, Buffer.from(JSON.stringify({schemaVersion: 1, ...metadata, businessContext, entries}, null, 2)));},
    publicSummary() {return entries.map(({request, ...entry}) => ({...entry, response: entry.response && {...entry.response, body: {sha256: entry.response.body.sha256, bytes: entry.response.body.bytes}}}));},
  };
}
