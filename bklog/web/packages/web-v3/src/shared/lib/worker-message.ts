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

/**
 * @file event bus
 * @author  <>
 */

import { toRaw } from 'vue';
// Vue3 proxies cannot cross structured-clone boundaries. Preserve the message's data shape.
export function toWorkerMessage(value, seen = new WeakMap()) {
  if (!value || typeof value !== 'object') return value;
  const raw = toRaw(value);
  if (seen.has(raw)) return seen.get(raw);
  if (raw instanceof Date || raw instanceof RegExp || raw instanceof ArrayBuffer || ArrayBuffer.isView(raw) || (typeof Blob !== 'undefined' && raw instanceof Blob)) return raw;
  if (raw instanceof Map) {
    const result = new Map(); seen.set(raw, result);
    for (const [key, item] of raw) result.set(toWorkerMessage(key, seen), toWorkerMessage(item, seen));
    return result;
  }
  if (raw instanceof Set) {
    const result = new Set(); seen.set(raw, result);
    for (const item of raw) result.add(toWorkerMessage(item, seen));
    return result;
  }
  const result = Array.isArray(raw) ? new Array(raw.length) : {};
  seen.set(raw, result);
  for (const key of Object.keys(raw)) result[key] = toWorkerMessage(raw[key], seen);
  return result;
}
