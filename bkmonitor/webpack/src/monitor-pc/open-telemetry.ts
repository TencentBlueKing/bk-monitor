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

import Vue from 'vue';

import { BkOpenTelemetry } from '@blueking/open-telemetry';
import { vueRouter3Source } from '@blueking/open-telemetry/vue-router3';

import type VueRouter from 'vue-router';
import type { Store } from 'vuex';

/** 机器人信息轮询接口：不采集、不计入页面活动窗口 */
const ROBOT_INFO_URL = 'commons/fetch_robot_info/';

/**
 * 按 pathname 末尾排除轮询请求。host、静态资源前缀、query、hash 不影响判断。
 * 新增排除项时只追加路径，并同时作用于请求采集与页面活动窗口。
 */
const IGNORED_POLLING_PATHS = ['/static_version.txt', '/notice/announcements'];

const isIgnoredPollingUrl = (url: string): boolean => {
  try {
    const pathname = new URL(url, window.location.href).pathname.replace(/\/+$/, '');
    return IGNORED_POLLING_PATHS.some(path => pathname.endsWith(path));
  } catch {
    return false;
  }
};

const redactRumUrl = (url: string): string => {
  if (!url) return '';
  try {
    const parsed = new URL(url, window.location.href);
    parsed.username = '';
    parsed.password = '';
    parsed.search = '';
    // 分享凭据既可能在 pathname 中，也可能在 hash 路由中。
    const maskShareToken = (path: string) => path.replace(/(\/share\/)[^/]+/gi, '$1***');
    parsed.pathname = maskShareToken(parsed.pathname);
    parsed.hash = maskShareToken(parsed.hash.match(/^#!?\/[^?#]*/)?.[0] || '');
    return parsed.href;
  } catch {
    return '';
  }
};

export let bkOTInstance: BkOpenTelemetry | undefined;

const getComponentStack = (vm: null | Vue) => {
  const names: string[] = [];
  for (let component = vm; component && names.length < 20; component = component.$parent) {
    names.push(component.$options.name || 'AnonymousComponent');
  }
  return names.join('\n');
};

// 初始化蓝鲸 RUM 上报 SDK，仅在后端下发 window.rum.enabled 且提供 endpoint 时启用
export const initOpenTelemetry = (
  router: VueRouter,
  store: Store<unknown>,
  apiBaseUrl?: string
): BkOpenTelemetry | undefined => {
  if (bkOTInstance) return bkOTInstance;
  if (!window.rum?.enabled || !window.rum.endpoint) return;

  const cleanupCallbacks: Array<() => void> = [];
  const forwardingVueErrors = new Set<unknown>();
  const originalConsoleError = window.console.error.bind(window.console);
  let appReadyReported = false;

  // 构造后默认 autoStart；session.sampleRate 默认 1（全量）
  const instance: BkOpenTelemetry = new BkOpenTelemetry({
    application: {
      name: 'bk-monitor',
      environment: process.env.NODE_ENV,
      version: window.footer_version,
    },
    transport: {
      endpoint: window.rum.endpoint,
      token: window.rum.token,
    },
    privacy: {
      redactUrl: redactRumUrl,
    },
    tracking: {
      view: {
        // 使用成功导航与路由模板，保留 :appName 等参数名；同页查询条件变化不新建 View。
        source: vueRouter3Source(router),
        // 轮询类请求不延长 View Loading Time
        excludedActivityUrls: [ROBOT_INFO_URL, isIgnoredPollingUrl],
      },
      request: {
        excludedUrls: [ROBOT_INFO_URL, isIgnoredPollingUrl],
        // 复用 Axios 的实际 API 基地址，跨域仅放行该路径及其子路径。
        allowedTracingUrls: [
          window.location.origin,
          ...(apiBaseUrl ? [new URL(apiBaseUrl, window.location.href).href] : []),
        ],
      },
      blankScreen: {
        // SPA 挂载根节点，避免对整页 body 误判白屏
        rootSelector: '#app',
      },
      longTask: true,
      error: { captureConsole: true },
      cspViolation: true,
      websocket: true,
      beforeSend: (event, context) => {
        // 原 Vue handler 仍可打印错误，同次转发不再生成第二条 console 错误。
        if (
          context.type === 'error' &&
          event.attributes['error.source'] === 'console' &&
          forwardingVueErrors.has(context.error)
        )
          return false;
      },
    },
    context: {
      user: { id: window.username },
    },
    extensions: {
      plugins: [
        {
          name: 'monitor-vue-context',
          init() {
            let active = true;
            let previousBizId: number | undefined;
            const trackBusinessSwitch = (reportSwitch = false) => {
              const rawBizId = store.getters.bizId;
              const bizId =
                rawBizId !== '' && rawBizId != null && Number.isFinite(Number(rawBizId)) ? Number(rawBizId) : undefined;
              if (reportSwitch && previousBizId !== undefined && bizId !== undefined && bizId !== previousBizId) {
                instance.reportAction({
                  name: 'switch_business',
                  attributes: { 'bk.previous_biz_id': previousBizId, 'bk.target_biz_id': bizId },
                });
              }
              previousBizId = bizId;
            };
            trackBusinessSwitch();
            cleanupCallbacks.push(
              store.subscribe(mutation => {
                if (mutation.type === 'app/SET_BIZ_ID' || mutation.type === 'app/SET_APP_STATE') {
                  trackBusinessSwitch(mutation.type === 'app/SET_BIZ_ID');
                }
              })
            );

            const previousErrorHandler = Vue.config.errorHandler;
            const errorHandler: typeof Vue.config.errorHandler = (error, vm, info) => {
              forwardingVueErrors.add(error);
              try {
                instance.reportError(error, {
                  componentStack: getComponentStack(vm),
                  attributes: { 'error.framework': 'vue', 'vue.info': info },
                });
              } finally {
                try {
                  if (previousErrorHandler) previousErrorHandler.call(null, error, vm, info);
                  else originalConsoleError(error);
                } finally {
                  forwardingVueErrors.delete(error);
                }
              }
            };
            Vue.config.errorHandler = errorHandler;
            cleanupCallbacks.push(() => {
              active = false;
              if (Vue.config.errorHandler === errorHandler) Vue.config.errorHandler = previousErrorHandler;
            });

            // 首次导航完成且 Vue 更新 DOM 后记录里程碑；撤权/卸载后的回调不补报。
            router.onReady(() => {
              void Vue.nextTick(() => {
                if (!active || appReadyReported || !instance.isViewActive()) return;
                appReadyReported = true;
                instance.addTiming('app_ready');
                instance.reportCustomEvent({ name: 'app_ready' });
              });
            });
          },
          shutdown() {
            while (cleanupCallbacks.length) cleanupCallbacks.pop()?.();
          },
        },
      ],
    },
  });
  bkOTInstance = instance;
  return instance;
};
