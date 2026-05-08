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

export interface RouteChangeEvent {
  fromUrl: string;
  source: RouteChangeSource;
  toUrl: string;
}

export type RouteChangeSource = 'hashchange' | 'popstate' | 'pushState' | 'replaceState';

type RouteChangeHandler = (event: RouteChangeEvent) => void;

const subscribers = new Set<RouteChangeHandler>();

let lastUrl = '';
let originalPushState: typeof history.pushState | undefined;
let originalReplaceState: typeof history.replaceState | undefined;
let patched = false;

const getCurrentUrl = () => (typeof location === 'undefined' ? '' : location.href);

const emitRouteChange = (source: RouteChangeSource, fromUrl: string) => {
  const toUrl = getCurrentUrl();
  lastUrl = toUrl;
  const event: RouteChangeEvent = { fromUrl, source, toUrl };

  for (const subscriber of Array.from(subscribers)) {
    subscriber(event);
  }
};

const onPopState = () => {
  emitRouteChange('popstate', lastUrl || getCurrentUrl());
};

const onHashChange = () => {
  emitRouteChange('hashchange', lastUrl || getCurrentUrl());
};

const patchHistory = () => {
  if (patched || typeof window === 'undefined' || typeof history === 'undefined') {
    return;
  }

  patched = true;
  lastUrl = getCurrentUrl();
  originalPushState = history.pushState;
  originalReplaceState = history.replaceState;

  history.pushState = function patchedPushState(this: History, data: any, title: string, url?: null | string | URL) {
    const fromUrl = lastUrl || getCurrentUrl();
    const result = originalPushState?.apply(this, [data, title, url]);
    emitRouteChange('pushState', fromUrl);
    return result;
  };
  history.replaceState = function patchedReplaceState(
    this: History,
    data: any,
    title: string,
    url?: null | string | URL
  ) {
    const fromUrl = lastUrl || getCurrentUrl();
    const result = originalReplaceState?.apply(this, [data, title, url]);
    emitRouteChange('replaceState', fromUrl);
    return result;
  };
  window.addEventListener('popstate', onPopState);
  window.addEventListener('hashchange', onHashChange);
};

const restoreHistory = () => {
  if (!patched || typeof window === 'undefined' || typeof history === 'undefined') {
    return;
  }

  if (originalPushState) {
    history.pushState = originalPushState;
  }
  if (originalReplaceState) {
    history.replaceState = originalReplaceState;
  }
  window.removeEventListener('popstate', onPopState);
  window.removeEventListener('hashchange', onHashChange);
  originalPushState = undefined;
  originalReplaceState = undefined;
  patched = false;
  lastUrl = '';
};

export const subscribeRouteChange = (handler: RouteChangeHandler) => {
  if (typeof window === 'undefined' || typeof history === 'undefined') {
    return () => {};
  }

  patchHistory();
  subscribers.add(handler);

  return () => {
    subscribers.delete(handler);
    if (subscribers.size === 0) {
      restoreHistory();
    }
  };
};
