/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition):
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

import type { KeyValuePair, Span, TNil } from '../typings';

export default function filterSpans(textFilter: string, spans: Span[] | TNil) {
  if (!spans) {
    return null;
  }

  // if a span field includes at least one filter in includeFilters, the span is a match
  const includeFilters: string[] = [];

  // values with keys that include text in any one of the excludeKeys will be ignored
  const excludeKeys: string[] = [];

  // split textFilter by whitespace, remove empty strings, and extract includeFilters and excludeKeys
  textFilter
    .split(/\s+/)
    .filter(Boolean)
    .forEach(w => {
      if (w[0] === '-') {
        excludeKeys.push(w.substr(1).toLowerCase());
      } else {
        includeFilters.push(w.toLowerCase());
      }
    });

  const isTextInFilters = (filters: Array<string>, text: string) =>
    filters.some(filter => text.toLowerCase().includes(filter));

  const isTextInKeyValues = (kvs: Array<KeyValuePair>) =>
    kvs
      ? kvs.some(kv => {
          // ignore checking key and value for a match if key is in excludeKeys
          if (isTextInFilters(excludeKeys, kv.key)) return false;
          // match if key or value matches an item in includeFilters
          return isTextInFilters(includeFilters, kv.key) || isTextInFilters(includeFilters, kv.value.toString());
        })
      : false;

  const isSpanAMatch = (span: Span) =>
    isTextInFilters(includeFilters, span.operationName) ||
    isTextInFilters(includeFilters, span.process.serviceName) ||
    isTextInKeyValues(span.tags) ||
    // eslint-disable-next-line @typescript-eslint/prefer-optional-chain
    (span.logs !== null && span.logs.some(log => isTextInKeyValues(log.fields))) ||
    isTextInKeyValues(span.process.tags) ||
    includeFilters.some(filter => filter.replace(/^0*/, '') === span.spanID.replace(/^0*/, ''));

  // declare as const because need to disambiguate the type
  const rv: Set<string> = new Set(spans.filter(isSpanAMatch).map((span: Span) => span.spanID));
  return rv;
}
