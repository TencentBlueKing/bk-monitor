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
import { BkOpenTelemetry } from '@blueking/open-telemetry';

/** 机器人信息轮询接口：不采集、不计入页面活动窗口 */
const ROBOT_INFO_URL = 'commons/fetch_robot_info/';

/** hash / history 路由统一归一为低基数 path group */
const getPathGroup = (url: string): string => {
  const parsed = new URL(url, window.location.href);
  const hashLocation = parsed.hash.replace(/^#!?/, '');

  const pathname = hashLocation.startsWith('/') ? new URL(hashLocation, parsed.origin).pathname : parsed.pathname;

  return pathname.replace(/\/[0-9a-f]{8}-[0-9a-f-]{27,}/gi, '/:id').replace(/\/\d+(?=\/|$)/g, '/:id');
};

// 初始化蓝鲸 RUM 上报 SDK，仅在后端下发 window.rum.enabled 且提供 endpoint 时启用
export const initOpenTelemetry = (): BkOpenTelemetry | undefined => {
  if (!window.rum?.enabled || !window.rum.endpoint) return;

  // 构造后默认 autoStart；session.sampleRate 默认 1（全量）
  return new BkOpenTelemetry({
    application: {
      name: 'bk-monitor',
      environment: process.env.NODE_ENV,
      version: window.footer_version,
    },
    transport: {
      endpoint: window.rum.endpoint,
      token: window.rum.token,
      // 仅上报 Trace，关闭 Metric / Log
      signals: {
        metrics: false,
        logs: false,
      },
    },
    privacy: {
      // 脱敏 URL 中的常见敏感查询参数
      redactUrl: url => url.replace(/([?&](?:token|bk_ticket|access_token)=)[^&]+/gi, '$1***'),
    },
    tracking: {
      view: {
        getPathGroup,
        // 轮询类请求不延长 View Loading Time
        excludedActivityUrls: [ROBOT_INFO_URL],
      },
      request: {
        excludedUrls: [ROBOT_INFO_URL],
      },
      blankScreen: {
        // SPA 挂载根节点，避免对整页 body 误判白屏
        rootSelector: '#app',
      },
      longTask: true,
    },
    context: {
      user: { id: window.username },
      attributes: {
        // 事件上报时读取，覆盖异步就绪后的业务 ID
        page: () => ({
          bizId: window.cc_biz_id || window.bk_biz_id,
        }),
        metric: () => ({
          bizId: window.cc_biz_id || window.bk_biz_id,
        }),
      },
    },
  });
};

// 导出实例，供业务在异步拿到用户信息后通过 setUser 补充 user.id
export const bkOTInstance = initOpenTelemetry();
