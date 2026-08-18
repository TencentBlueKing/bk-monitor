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
import { getUrlParam } from './utils';

/** 消息来源标识，父页面据此识别监控平台发出的消息 */
const MESSAGE_SOURCE = 'bk-monitor';
/** 向父页面广播路由变化的消息类型 */
const ROUTE_CHANGE_TYPE = 'route-change';
/** 父页面下发参数联动的消息类型 */
const SET_PARAMS_TYPE = 'set-params';
/** 广播节流间隔，用于合并一次交互内的多次 URL 写回 */
const BROADCAST_THROTTLE = 100;
/** 分享视图的 hash 前缀，其 URL 携带免登 token，禁止广播给父页面 */
const SHARE_HASH_REGEX = /^#?\/share\//;

type ExternalParamsHandler = (params: Record<string, string>) => void;

interface IRouteChangeMessage {
  hash: string;
  href: string;
  query: Record<string, string>;
  source: typeof MESSAGE_SOURCE;
  type: typeof ROUTE_CHANGE_TYPE;
}

const noop = () => {};

let parentOrigin = '';
let lastFingerprint = '';
let broadcastTimer: null | number = null;
let broadcastInited = false;
let receiverInited = false;
const externalParamsHandlers = new Set<ExternalParamsHandler>();

/** weweb 沙箱下 window 被代理，取真实 window 才能拿到正确的父窗口引用 */
const getHostWindow = (): Window => window.rawWindow || window;

/** 是否被其他页面以 iframe 嵌入 */
const isEmbedded = (): boolean => {
  const hostWindow = getHostWindow();
  try {
    return hostWindow.self !== hostWindow.top;
  } catch {
    // 跨域嵌入下访问 top 可能抛 SecurityError，能走到这里说明必然处于 iframe 内
    return true;
  }
};

/**
 * 父页面 origin 由嵌入方通过 parentOrigin 参数声明，校验通过才开启通道。
 * 与 needMenu / readonly 等嵌入参数保持一致，取自 location.search。
 */
const resolveParentOrigin = (): string => {
  const value = getUrlParam('parentOrigin', false);
  if (!value) return '';
  try {
    const { origin, protocol } = new URL(decodeURIComponent(value));
    return /^https?:$/.test(protocol) ? origin : '';
  } catch {
    return '';
  }
};

const parseHashQuery = (hash: string): Record<string, string> => {
  const query: Record<string, string> = {};
  const search = hash.replace(/^#/, '').split('?')[1];
  if (!search) return query;
  new URLSearchParams(search).forEach((value, key) => {
    query[key] = value;
  });
  return query;
};

/** 仪表盘写回 URL 时每次都带随机 key，剔除后比对才能识别出真实的状态变化 */
const getStateFingerprint = (hash: string): string => {
  const [path, search = ''] = hash.replace(/^#/, '').split('?');
  const params = new URLSearchParams(search);
  params.delete('key');
  params.sort();
  return `${path}?${params.toString()}`;
};

const broadcast = () => {
  const { hash, href } = location;
  if (SHARE_HASH_REGEX.test(hash)) return;
  const fingerprint = getStateFingerprint(hash);
  if (fingerprint === lastFingerprint) return;
  lastFingerprint = fingerprint;
  const message: IRouteChangeMessage = {
    hash,
    href,
    query: parseHashQuery(hash),
    source: MESSAGE_SOURCE,
    type: ROUTE_CHANGE_TYPE,
  };
  getHostWindow().parent.postMessage(message, parentOrigin);
};

const scheduleBroadcast = () => {
  if (broadcastTimer !== null) return;
  broadcastTimer = window.setTimeout(() => {
    broadcastTimer = null;
    broadcast();
  }, BROADCAST_THROTTLE);
};

/** vue-router 的 hash 模式通过 pushState / replaceState 改 hash，不会触发 hashchange，只能劫持方法感知 */
const patchHistory = () => {
  const { pushState, replaceState } = history;
  history.pushState = (...args: Parameters<History['pushState']>) => {
    pushState.apply(history, args);
    scheduleBroadcast();
  };
  history.replaceState = (...args: Parameters<History['replaceState']>) => {
    replaceState.apply(history, args);
    scheduleBroadcast();
  };
};

const notifyExternalParams = (params: Record<string, string>) => {
  for (const handler of externalParamsHandlers) {
    handler(params);
  }
};

const handleParentMessage = (event: MessageEvent) => {
  if (event.origin !== parentOrigin) return;
  const { payload, type } = event.data || {};
  if (type !== SET_PARAMS_TYPE || !payload || typeof payload !== 'object') return;
  notifyExternalParams(payload);
};

/** 父页面改 iframe.src 的 hash 时只触发 hashchange，vue-router 不监听该事件，需要在这里补上 */
const handleHashChange = () => {
  notifyExternalParams(parseHashQuery(location.hash));
};

/**
 * 开启向父页面广播路由变化的通道，仅在被 iframe 嵌入且声明了合法 parentOrigin 时生效。
 * 只需在顶层应用入口调用一次：微前端子应用与主壳共享同一份 history，子应用内的跳转同样会被感知。
 */
export const initIframeBroadcast = () => {
  if (broadcastInited) return;
  parentOrigin = resolveParentOrigin();
  if (!parentOrigin || !isEmbedded()) return;
  broadcastInited = true;
  patchHistory();
  window.addEventListener('popstate', scheduleBroadcast);
  window.addEventListener('hashchange', scheduleBroadcast);
  broadcast();
};

/**
 * 订阅父页面下发的参数联动，返回取消订阅函数。
 * 同时兼容 postMessage 与直接修改 iframe hash 两种下发方式，订阅方需自行按值比对后再决定是否刷新。
 */
export const onExternalParams = (handler: ExternalParamsHandler): (() => void) => {
  if (!receiverInited) {
    parentOrigin = parentOrigin || resolveParentOrigin();
    if (!parentOrigin || !isEmbedded()) return noop;
    receiverInited = true;
    window.addEventListener('message', handleParentMessage);
    window.addEventListener('hashchange', handleHashChange);
  }
  externalParamsHandlers.add(handler);
  return () => {
    externalParamsHandlers.delete(handler);
  };
};
