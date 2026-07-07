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

// 初始化蓝鲸 RUM 上报 SDK，仅在后端下发 window.rum.enabled 且提供 endpoint 时启用
export const initOpenTelemetry = () => {
  if (!window.rum?.enabled || !window.rum.endpoint) return;
  // 构造后默认 autoStart，采集页面访问、接口、资源、JS 错误、Web Vitals 等并通过 OTLP 上报
  return new BkOpenTelemetry({
    app: {
      name: 'bk-monitor',
      environment: process.env.NODE_ENV,
      version: window.footer_version,
    },
    transport: {
      endpoint: window.rum.endpoint,
      token: window.rum.token,
    },
    user: {
      id: window.username,
    },
  });
};

// 导出实例，供业务在异步拿到用户信息后通过 setUser 补充 user.id
export const bkOTInstance = initOpenTelemetry();
