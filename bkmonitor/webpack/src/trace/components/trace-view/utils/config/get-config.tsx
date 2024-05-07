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
import memoizeOne from 'memoize-one';

import defaultConfig, { deprecations } from '../../constants/default-config';
import processDeprecation from './process-deprecation';

let haveWarnedFactoryFn = false;
let haveWarnedDeprecations = false;

/**
 * Merge the embedded config from the query service (if present) with the
 * default config from `../../constants/default-config`.
 */
const getConfig = memoizeOne(() => {
  const { getJaegerUiConfig } = window;
  if (typeof getJaegerUiConfig !== 'function') {
    if (!haveWarnedFactoryFn) {
      console.warn('Embedded config not available');
      haveWarnedFactoryFn = true;
    }
    return { ...defaultConfig };
  }
  const embedded = getJaegerUiConfig();
  if (!embedded) {
    return { ...defaultConfig };
  }
  // check for deprecated config values
  if (Array.isArray(deprecations)) {
    deprecations.forEach(deprecation => processDeprecation(embedded, deprecation, !haveWarnedDeprecations));
    haveWarnedDeprecations = true;
  }
  const rv = { ...defaultConfig, ...embedded };
  // __mergeFields config values should be merged instead of fully replaced
  const keys = defaultConfig.__mergeFields || [];
  // eslint-disable-next-line @typescript-eslint/prefer-for-of
  for (let i = 0; i < keys.length; i++) {
    const key = keys[i];
    if (typeof embedded[key] === 'object' && embedded[key] !== null) {
      rv[key] = { ...defaultConfig[key], ...embedded[key] };
    }
  }
  return rv;
});

export default getConfig;

export function getConfigValue(path: string) {
  return _get(getConfig(), path);
}
