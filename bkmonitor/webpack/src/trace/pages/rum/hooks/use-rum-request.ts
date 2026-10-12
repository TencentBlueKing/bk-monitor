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
import { onScopeDispose, shallowRef } from 'vue';

/** RUM 独立数据区域：保留上次结果，只允许最后一次请求更新数据和状态。 */
export function useRumRequest<T>(request: (signal: AbortSignal) => Promise<T>, initialData: T) {
  const data = shallowRef<T>(initialData);
  const loading = shallowRef(false);
  const error = shallowRef(false);
  let controller: AbortController | null = null;
  let disposed = false;

  async function run() {
    if (disposed) return;
    controller?.abort();
    controller = new AbortController();
    const { signal } = controller;
    loading.value = true;
    error.value = false;
    try {
      const result = await request(signal);
      if (!signal.aborted) data.value = result;
    } catch {
      if (!signal.aborted) error.value = true;
    } finally {
      if (!signal.aborted) loading.value = false;
    }
  }

  onScopeDispose(() => {
    disposed = true;
    controller?.abort();
  });

  return { data, loading, error, run };
}
