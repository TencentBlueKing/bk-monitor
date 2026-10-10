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

const REQUEST_ID_RE = /\b([0-9a-f]{32})\b/i;
const TRACE_ID_RE = /^00-([0-9a-f]{32})-/i;
const PREFIX_REQUEST_ID_RE = /^\s*([0-9a-f]{32})\s*[：:]/i;

const KAFKA_TAIL_RE = /kafka_tail|failed to get partitions|databus_collectors\/(?:[^/\s]+\/)?tail/i;

function extractRequestId(message, traceparent) {
  const fromTrace = `${traceparent || ''}`.match(TRACE_ID_RE);
  if (fromTrace?.[1]) {
    return fromTrace[1];
  }
  const text = `${message || ''}`;
  const fromPrefix = text.match(PREFIX_REQUEST_ID_RE);
  if (fromPrefix?.[1]) {
    return fromPrefix[1];
  }
  const fromBody = text.match(REQUEST_ID_RE);
  return fromBody?.[1] || '';
}

function isInternalApiDump(message) {
  const text = `${message || ''}`;
  if (!text.trim()) {
    return false;
  }
  return (
    /path\s*=>/i.test(text) ||
    /\[(?:log_search|metadata)[^\]]*API\]/i.test(text) ||
    /\/api\/(?:bk-monitor|c\/compapi)/i.test(text) ||
    KAFKA_TAIL_RE.test(text)
  );
}

function parseCollectorApiError(message, traceparent) {
  const original = `${message || ''}`.trim();
  const requestId = extractRequestId(original, traceparent);
  if (!original) {
    return { kind: null, requestId, original };
  }
  if (KAFKA_TAIL_RE.test(original)) {
    return { kind: 'kafka_tail', requestId, original };
  }
  if (isInternalApiDump(original)) {
    return { kind: 'internal_dump', requestId, original };
  }
  return { kind: null, requestId, original };
}

module.exports = {
  extractRequestId,
  isInternalApiDump,
  parseCollectorApiError,
};
