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

import type { NormalizedBkOTConfig } from './config';

// 在 sessionStorage 不可用时降级到模块内单例缓存，避免同会话内多次结果不一致
const memoryCache = new Map<string, boolean>();

const readMemory = (key: string) => memoryCache.get(key);
const writeMemory = (key: string, value: boolean) => {
  memoryCache.set(key, value);
  return value;
};

export const isBkOTSampled = (config: Pick<NormalizedBkOTConfig, 'sampleRate' | 'sampleStorageKey'>) => {
  const { sampleRate, sampleStorageKey } = config;

  if (sampleRate <= 0) {
    return false;
  }
  if (sampleRate >= 1) {
    return true;
  }

  try {
    const cached = sessionStorage.getItem(sampleStorageKey);
    if (cached) {
      return cached === '1';
    }
    const sampled = Math.random() < sampleRate;
    sessionStorage.setItem(sampleStorageKey, sampled ? '1' : '0');
    writeMemory(sampleStorageKey, sampled);
    return sampled;
  } catch {
    const cached = readMemory(sampleStorageKey);
    if (typeof cached === 'boolean') {
      return cached;
    }
    return writeMemory(sampleStorageKey, Math.random() < sampleRate);
  }
};
