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

import { dissolveSkeleton } from '@/shared/ui/loading/presence';

let topMenuSettled = false;
const menuListeners = new Set<() => void>();
export const isTopMenuSettled = () => topMenuSettled;
export const markTopMenuSettled = () => {
  if (topMenuSettled) return;
  topMenuSettled = true;
  menuListeners.forEach(listener => listener());
  menuListeners.clear();
};
export const whenTopMenuSettled = (callback: () => void) => {
  if (topMenuSettled) { callback(); return () => {}; }
  menuListeners.add(callback);
  return () => { menuListeners.delete(callback); };
};

let bootstrapShellReleased = false;
export const isBootstrapShellReleased = () => bootstrapShellReleased;
const cleanupShell = (shell: HTMLElement) => {
  if (shell.dataset.bodyReleased === '1' && shell.dataset.navReleased === '1') shell.remove();
};

/** Mounted navigation takes ownership of its own independently pending regions. */
export const releaseBootstrapNavWhenReady = () => {
  const shell = document.querySelector<HTMLElement>('.bklog-bootstrap-loading');
  if (!shell || shell.dataset.navReleased) return;
  if (!document.querySelector('.log-search-nav') && !bootstrapShellReleased) return;
  shell.dataset.navReleased = 'leaving';
  const nav = shell.querySelector<HTMLElement>('.bklog-bootstrap-loading__nav');
  const finish = () => {
    if (nav) { nav.style.visibility = 'hidden'; nav.style.pointerEvents = 'none'; }
    shell.dataset.navReleased = '1';
    cleanupShell(shell);
  };
  if (nav) dissolveSkeleton(nav, finish); else finish();
};

let retrieveShellSettler: (() => void) | null = null;
export const bindRetrieveShellSettle = (settler: () => void) => { retrieveShellSettler = settler; };
export const requestRetrieveShellSettle = () => { retrieveShellSettler?.(); };
export const unbindRetrieveShellSettle = (settler: () => void) => {
  if (retrieveShellSettler === settler) retrieveShellSettler = null;
};

/** Body readiness is independent of menu/results. Dissolve only the HTML overlay. */
export const releaseBootstrapShell = () => {
  if (bootstrapShellReleased) return;
  bootstrapShellReleased = true;
  const shell = document.querySelector<HTMLElement>('.bklog-bootstrap-loading');
  if (!shell) return;
  shell.dataset.bodyReleased = 'leaving';
  const body = shell.querySelector<HTMLElement>('.bklog-bootstrap-loading__body');
  const finish = () => {
    body?.remove();
    shell.dataset.bodyReleased = '1';
    cleanupShell(shell);
  };
  if (body) dissolveSkeleton(body, finish); else finish();
  // Headless / redirected routes may never mount the main navigation.
  if (!document.querySelector('.log-search-nav')) releaseBootstrapNavWhenReady();
};
