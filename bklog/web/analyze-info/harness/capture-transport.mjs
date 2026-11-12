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

/** A uniquely identified CDP body fallback; it never reissues a business request. */
export async function createCaptureTransport(context, clockEpochMs) {
  const page = await context.newPage();
  await page.clock.setFixedTime(new Date(clockEpochMs));
  const cdp = await context.newCDPSession(page);
  const requests = [];
  cdp.on('Network.requestWillBeSent', event => requests.push({id: event.requestId, url: event.request.url, method: event.request.method, body: event.request.postData ?? null}));
  await cdp.send('Network.enable', {maxTotalBufferSize: 256 * 1024 * 1024, maxResourceBufferSize: 128 * 1024 * 1024, enableDurableMessages: true});
  return {page, async bodyFallback(request) {
    const candidates = requests.filter(r => r.url === request.url() && r.method === request.method() && r.body === request.postData());
    const ids = [...new Set(candidates.map(r => r.id))];
    if (ids.length !== 1) throw new Error('BODY_FALLBACK_AMBIGUOUS_TRANSPORT_ID');
    const result = await cdp.send('Network.getResponseBody', {requestId: ids[0]});
    return {body: Buffer.from(result.body, result.base64Encoded ? 'base64' : 'utf8'), transport: {source: 'CDP_UNIQUE_REQUEST_ID', requestId: ids[0]}};
  }};
}
