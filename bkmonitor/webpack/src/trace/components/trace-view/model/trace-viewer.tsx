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

import _memoize from 'lodash/memoize';

import type { Span } from '../typings';

// eslint-disable-next-line @typescript-eslint/naming-convention
export function _getTraceNameImpl(spans: Span[]) {
  // Use a span with no references to another span in given array
  // prefering the span with the fewest references
  // using start time as a tie breaker
  let candidateSpan: Span | undefined;
  const allIDs: Set<string> = new Set(spans.map(({ spanID }) => spanID));

  // eslint-disable-next-line @typescript-eslint/prefer-for-of
  for (let i = 0; i < spans.length; i++) {
    const hasInternalRef = !!spans[i].references?.some(
      ({ traceID, spanID }) => traceID === spans[i].traceID && allIDs.has(spanID)
    );
    if (hasInternalRef) continue;

    if (!candidateSpan) {
      candidateSpan = spans[i];
      continue;
    }

    // eslint-disable-next-line @typescript-eslint/prefer-optional-chain
    const thisRefLength = (spans[i].references && spans[i].references.length) || 0;
    // eslint-disable-next-line @typescript-eslint/prefer-optional-chain
    const candidateRefLength = (candidateSpan.references && candidateSpan.references.length) || 0;

    if (
      thisRefLength < candidateRefLength ||
      (thisRefLength === candidateRefLength && spans[i].startTime < candidateSpan.startTime)
    ) {
      candidateSpan = spans[i];
    }
  }
  return candidateSpan ? `${candidateSpan.process.serviceName}: ${candidateSpan.operationName}` : '';
}

export const getTraceName = _memoize(_getTraceNameImpl, (spans: Span[]) => {
  if (!spans.length) return 0;
  return spans[0].traceID;
});
