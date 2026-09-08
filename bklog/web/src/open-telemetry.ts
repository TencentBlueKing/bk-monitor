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
import { BkOpenTelemetry } from '@blueking/open-telemetry';

/** 日志提取任务轮询：不采集、不计入页面活动窗口 */
const EXTRACT_POLLING_URL = 'log_extract/tasks/polling/';

/** 开发态环境变量接口只下发 BKAPP_RUM_*，生产态 HTML 已注入 window.rum */
export const hydrateRumWindow = () => {
  if (window.rum) {
    return;
  }

  window.rum = {
    enabled: String(window.BKAPP_RUM_ENABLED).toLowerCase() === 'true',
    sdk: window.BKAPP_RUM_SDK || 'otlp',
    endpoint: window.BKAPP_RUM_ENDPOINT || '',
    token: window.BKAPP_RUM_TOKEN || '',
  };
};

/** hash / history 路由统一归一为低基数 path group */
export const getUrlTemplate = (url: string): string => {
  const parsed = new URL(url, window.location.href);
  const hashLocation = parsed.hash.replace(/^#!?/, '');

  const pathname = hashLocation.startsWith('/') ? new URL(hashLocation, parsed.origin).pathname : parsed.pathname;

  return pathname.replace(/\/[0-9a-f]{8}-[0-9a-f-]{27,}/gi, '/:id').replace(/\/\d+(?=\/|$)/g, '/:id');
};

export const redactRumUrl = (url: string): string =>
  url.replace(/([?&](?:token|bk_ticket|access_token)=)[^&]+/gi, '$1***');

export const canStartRum = (): boolean => {
  hydrateRumWindow();
  return Boolean(!window.__IS_MONITOR_COMPONENT__ && window.rum?.enabled && window.rum.endpoint);
};

export let bkOTInstance: BkOpenTelemetry | undefined;

// 初始化蓝鲸 RUM 上报 SDK，仅在后端下发 window.rum.enabled 且提供 endpoint 时启用
export const initOpenTelemetry = (): BkOpenTelemetry | undefined => {
  if (!canStartRum()) {
    return;
  }

  if (bkOTInstance) {
    return bkOTInstance;
  }

  // 构造后默认 autoStart；session.sampleRate 默认 1（全量）
  bkOTInstance = new BkOpenTelemetry({
    application: {
      name: 'bk-log',
      environment: process.env.NODE_ENV,
      version: window.VERSION,
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
        getUrlTemplate,
        excludedActivityUrls: [EXTRACT_POLLING_URL],
      },
      request: {
        excludedUrls: [EXTRACT_POLLING_URL],
        allowedTracingUrls: [url => new URL(url).origin === window.location.origin],
      },
      blankScreen: {
        rootSelector: '#app',
      },
      longTask: true,
    },
  });

  return bkOTInstance;
};
