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

let topMenuSettled = false;
let resolveTopMenuSettled: () => void = () => {};
const topMenuSettledPromise = new Promise<void>(resolve => {
  resolveTopMenuSettled = resolve;
});

/** 顶部菜单请求结束。检索首屏在此之前不揭开 HTML 骨架。 */
export const markTopMenuSettled = () => {
  if (topMenuSettled) {
    return;
  }
  topMenuSettled = true;
  resolveTopMenuSettled();
};

export const whenTopMenuSettled = (callback: () => void) => {
  if (topMenuSettled) {
    callback();
    return;
  }
  topMenuSettledPromise.then(callback);
};

let bootstrapShellReleased = false;

export const isBootstrapShellReleased = () => bootstrapShellReleased;

/** 顶栏内容已经稳定后，只揭开导航，正文骨架继续盖住结果区。 */
export const releaseBootstrapNavWhenReady = () => {
  const started = performance.now();
  const attempt = () => {
    if (bootstrapShellReleased || performance.now() - started > 8000) {
      return;
    }
    const shell = document.querySelector('.bklog-bootstrap-loading');
    if (!(shell instanceof HTMLElement)) {
      return;
    }
    const nav = document.querySelector('.log-search-nav');
    if (!(nav instanceof HTMLElement)) {
      requestAnimationFrame(attempt);
      return;
    }
    const bottom = Math.round(nav.getBoundingClientRect().bottom);
    if (bottom < 40) {
      requestAnimationFrame(attempt);
      return;
    }
    if (shell.dataset.navReleased === '1') {
      return;
    }
    shell.dataset.navReleased = '1';
    shell.querySelector('.bklog-bootstrap-loading__nav')?.remove();
    shell.style.top = `${bottom}px`;
  };
  attempt();
};

let retrieveShellSettler: (() => void) | null = null;

/** 检索页在 setup 里登记揭开骨架的回调，避免 provide 落到已挂载实例上。 */
export const bindRetrieveShellSettle = (settler: () => void) => {
  retrieveShellSettler = settler;
};

export const requestRetrieveShellSettle = () => {
  retrieveShellSettler?.();
};

export const unbindRetrieveShellSettle = (settler: () => void) => {
  if (retrieveShellSettler === settler) {
    retrieveShellSettler = null;
  }
};

/** 去掉首屏 HTML 骨架。只移除一次，避免顶栏被重复揭开。 */
export const releaseBootstrapShell = () => {
  if (bootstrapShellReleased) {
    return;
  }
  const loading = document.querySelector('.bklog-bootstrap-loading');
  if (!loading) {
    return;
  }
  bootstrapShellReleased = true;
  document.getElementById('app')?.classList.add('bklog-bootstrap-app-enter');
  loading.remove();
};
