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

import {requestPolicy} from './protocol.mjs';

/** Business calls never continue to the backend; unmatched calls fail closed. */
export async function installReplayTransport(context, {target, fixture, rules, sequence, entries, failures, cancellations, routeDecisions}) {
  let observationPhase = 'bootstrap';
  const requestMap = new WeakMap(), abortWaiters = new WeakMap();
  context.on('requestfinished', request => {const entry = requestMap.get(request);if (entry) entry.complete = true;});
  context.on('requestfailed', request => {
    const entry = requestMap.get(request);
    if (entry) {entry.failure = request.failure()?.errorText;entry.cancelled = /abort/i.test(entry.failure ?? '');}
    abortWaiters.get(request)?.();
  });
  await context.route('**/*', async route => {
    const request = route.request(), url = new URL(request.url());
    if (url.origin !== new URL(target).origin) {await route.abort('blockedbyclient');return;}
    const isBusiness = ['xhr', 'fetch', 'ping'].includes(request.resourceType()) || request.method() !== 'GET' || url.pathname.startsWith('/api/') || url.pathname === '/notice/announcements/';
    if (!isBusiness) {routeDecisions.push({action: 'FORWARD', kind: 'STATIC', path: url.pathname});await route.continue();return;}
    routeDecisions.push({action: 'INTERCEPT', kind: 'BUSINESS', path: url.pathname, method: request.method()});
    const policy = requestPolicy({url: request.url(), method: request.method()}, rules);
    if (policy.decision === 'BLOCK') {
      if (!fixture.exclusions.some(e => e.ruleId === policy.ruleId && e.path === url.pathname && e.method === request.method())) failures.push({reason: 'UNCLASSIFIED_REPLAY_DEPENDENCY', path: url.pathname, method: request.method()});
      await route.abort('blockedbyclient');return;
    }
    try {
      const record = sequence.consume({url: request.url(), method: request.method(), body: request.postData()}, observationPhase);
      const entry = {id: record.id, path: record.path, policy, complete: false, fixtureRecord: record};
      entries.push(entry);requestMap.set(request, entry);
      if (record.kind === 'EXPECTED_CLIENT_CANCEL') {
        let timer;
        const cancelled = await Promise.race([
          new Promise(resolve => abortWaiters.set(request, () => resolve(true))),
          new Promise(resolve => {timer = setTimeout(() => resolve(false), 15000);}),
        ]);
        clearTimeout(timer);
        cancellations.push({id: record.id, clientCancellationObserved: cancelled});
        if (!cancelled) failures.push({reason: 'EXPECTED_CLIENT_CANCEL_NOT_OBSERVED', id: record.id});
        await route.abort('aborted').catch(() => {});
        return;
      }
      // Preserve observed transport delay to exercise the same initialization races.
      await new Promise(resolve => setTimeout(resolve, Math.max(0, record.finishedAt - record.startedAt)));
      await route.fulfill({status: record.response.status, contentType: record.response.contentType, body: record.body});
    } catch (error) {
      failures.push({reason: error.message, path: url.pathname, method: request.method()});
      await route.abort('blockedbyclient').catch(() => {});
    }
  });
  return {phase(id) {if (typeof id !== 'string' || !id) throw new Error('REPLAY_PHASE_REQUIRED');observationPhase = id;}};
}
