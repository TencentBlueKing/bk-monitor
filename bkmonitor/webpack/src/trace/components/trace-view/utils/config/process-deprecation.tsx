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

import _get from 'lodash/get';
import _has from 'lodash/has';
import _set from 'lodash/set';
import _unset from 'lodash/unset';

interface IDeprecation {
  currentKey: string;
  formerKey: string;
}

/**
 * Processes a deprecated config property with respect to a configuration.
 * NOTE: This mutates `config`.
 *
 * If the deprecated config property is found to be set on `config`, it is
 * moved to the new config property unless a conflicting setting exists. If
 * `issueWarning` is `true`, warnings are issues when:
 *
 * - The deprecated config property is found to be set on `config`
 * - The value at the deprecated config property is moved to the new property
 * - The value at the deprecated config property is ignored in favor of the value at the new property
 */
export default function processDeprecation(
  config: Record<string, any>,
  deprecation: IDeprecation,
  issueWarning: boolean
) {
  const { formerKey, currentKey } = deprecation;
  if (_has(config, formerKey)) {
    let isTransfered = false;
    let isIgnored = false;
    if (!_has(config, currentKey)) {
      // the new key is not set so transfer the value at the old key
      const value = _get(config, formerKey);
      _set(config, currentKey, value);
      isTransfered = true;
    } else {
      isIgnored = true;
    }
    _unset(config, formerKey);

    if (issueWarning) {
      const warnings = [`"${formerKey}" is deprecated, instead use "${currentKey}"`];
      if (isTransfered) {
        warnings.push(`The value at "${formerKey}" has been moved to "${currentKey}"`);
      }
      if (isIgnored) {
        warnings.push(`The value at "${formerKey}" is being ignored in favor of the value at "${currentKey}"`);
      }

      console.warn(warnings.join('\n'));
    }
  }
}
