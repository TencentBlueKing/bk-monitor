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

import {toRaw} from 'vue';

/** Native structured clone for Vue3 form data. Only unwrap data containers;
 * preserve native handling/rejection of all other built-ins and values. */
export function cloneReactiveData<T>(value: T): T {
  const seen = new WeakMap<object, unknown>();
  function unwrap(input: unknown): unknown {
    if (input === null || typeof input !== 'object') return input;
    const raw = toRaw(input);
    if (seen.has(raw)) return seen.get(raw);
    if (raw instanceof Map) {
      const result = new Map<unknown, unknown>();seen.set(raw, result);
      for (const [key, item] of raw) result.set(unwrap(key), unwrap(item));
      return result;
    }
    if (raw instanceof Set) {
      const result = new Set<unknown>();seen.set(raw, result);
      for (const item of raw) result.add(unwrap(item));
      return result;
    }
    if (Array.isArray(raw) || Object.prototype.toString.call(raw) === '[object Object]') {
      const result: unknown[] | Record<string, unknown> = Array.isArray(raw) ? new Array(raw.length) : {};
      seen.set(raw, result);
      for (const key of Object.keys(raw)) Object.defineProperty(result, key, {
        value: unwrap((raw as Record<string, unknown>)[key]), enumerable: true, configurable: true, writable: true,
      });
      return result;
    }
    return raw;
  }
  return structuredClone(unwrap(value)) as T;
}
