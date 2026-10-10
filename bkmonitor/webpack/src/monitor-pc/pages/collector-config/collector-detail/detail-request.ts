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
export default class DetailRequest {
  private controller: AbortController = null;
  private version = 0;
  error = false;
  loaded = false;
  loading = false;

  cancel() {
    this.version += 1;
    this.controller?.abort();
    this.controller = null;
    this.loading = false;
  }

  async run<T>(fetch: (signal: AbortSignal) => Promise<T>, apply: (data: T) => void): Promise<boolean> {
    this.cancel();
    const version = this.version;
    const controller = new AbortController();
    this.controller = controller;
    this.loading = true;
    this.error = false;
    try {
      const data = await fetch(controller.signal);
      if (version !== this.version) return false;
      apply(data);
      this.loaded = true;
      return true;
    } catch {
      if (version === this.version && !controller.signal.aborted) this.error = true;
      return false;
    } finally {
      if (version === this.version) {
        this.loading = false;
        this.controller = null;
      }
    }
  }
}
