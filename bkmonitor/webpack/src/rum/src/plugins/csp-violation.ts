/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
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

import { SeverityNumber } from '@opentelemetry/api-logs';

import type { BkOTRumConfig } from '../core/config';
import type { BkOTPlugin } from '../core/plugin';

/**
 * 监听 CSP 违规事件并以 log 形式上报，便于排查脚本/资源被 CSP 拦截的问题。
 */
export const createCspViolationPlugin = (enabled: BkOTRumConfig['cspViolation']): BkOTPlugin => {
  let teardown: (() => void) | undefined;

  return {
    name: 'csp-violation',
    enabled: Boolean(enabled),
    init(context) {
      if (typeof window === 'undefined' || typeof document === 'undefined') {
        return;
      }

      const handler = (event: SecurityPolicyViolationEvent) => {
        context.emitLog({
          severityNumber: SeverityNumber.WARN,
          severityText: 'WARN',
          body: 'csp.violation',
          attributes: {
            ...context.config.getPageAttributes(),
            'csp.blocked_uri': context.config.redactUrl(event.blockedURI || ''),
            'csp.violated_directive': event.violatedDirective,
            'csp.effective_directive': event.effectiveDirective,
            'csp.original_policy': event.originalPolicy,
            'csp.disposition': event.disposition,
            'csp.source_file': context.config.redactUrl(event.sourceFile || ''),
            'csp.line_number': event.lineNumber,
            'csp.column_number': event.columnNumber,
            'csp.status_code': event.statusCode,
          },
        });
      };

      document.addEventListener('securitypolicyviolation', handler);
      teardown = () => document.removeEventListener('securitypolicyviolation', handler);
    },
    shutdown() {
      teardown?.();
      teardown = undefined;
    },
  };
};
