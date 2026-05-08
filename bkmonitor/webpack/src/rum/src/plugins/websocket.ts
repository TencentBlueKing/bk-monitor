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

import { SpanStatusCode } from '@opentelemetry/api';
import { SeverityNumber } from '@opentelemetry/api-logs';

import { shouldIgnoreUrl } from '../core/url';

import type { BkOTRumConfig } from '../core/config';
import type { BkOTPlugin } from '../core/plugin';

const getMessageByteLength = (data: unknown): number => {
  if (data == null) return 0;
  if (typeof data === 'string') {
    return typeof TextEncoder === 'undefined' ? data.length : new TextEncoder().encode(data).byteLength;
  }
  if (data instanceof ArrayBuffer) return data.byteLength;
  if (ArrayBuffer.isView(data)) return data.byteLength;
  if (typeof Blob !== 'undefined' && data instanceof Blob) return data.size;
  return 0;
};

const getWebSocketAttributes = (url: string, redactUrl: (url: string) => string) => {
  const spanAttributes: Record<string, string> = {
    'url.full': redactUrl(url),
    'network.protocol.name': 'websocket',
  };

  try {
    const parsed = new URL(url, typeof location === 'undefined' ? 'http://localhost' : location.href);
    spanAttributes['server.address'] = parsed.host;
  } catch {
    /* ignore malformed URL and keep the raw, redacted URL only */
  }

  return {
    spanAttributes,
    metricAttributes: {
      'network.protocol.name': 'websocket',
    },
  };
};

export const createWebSocketPlugin = (enabled: BkOTRumConfig['websocket']): BkOTPlugin => {
  let originalWebSocket: typeof WebSocket | undefined;

  return {
    name: 'websocket',
    enabled: Boolean(enabled),
    init(context) {
      if (typeof window === 'undefined' || typeof window.WebSocket === 'undefined') {
        return;
      }

      const NativeWebSocket = window.WebSocket;
      originalWebSocket = NativeWebSocket;

      const messageCounter = context.meter.createCounter('browser.websocket.message.count', {
        description: 'Total number of WebSocket messages observed',
      });
      const bytesCounter = context.meter.createCounter('browser.websocket.message.bytes', {
        unit: 'By',
        description: 'Total bytes transferred over WebSocket (best-effort)',
      });
      const errorCounter = context.meter.createCounter('browser.websocket.error.count', {
        description: 'Total number of WebSocket error events',
      });

      const PatchedWebSocket = function (this: WebSocket, url: string | URL, protocols?: string | string[]) {
        const urlValue = url.toString();

        // 用户主动 ignore 或上报 endpoint，避免回环监控
        if (shouldIgnoreUrl(context.config, urlValue)) {
          return protocols === undefined ? new NativeWebSocket(url) : new NativeWebSocket(url, protocols);
        }

        const { metricAttributes, spanAttributes } = getWebSocketAttributes(urlValue, context.config.redactUrl);
        // connect span 只覆盖"建立连接"阶段，避免长连接导致 span 永远不结束
        const connectSpan = context.startSpan('websocket.connect', spanAttributes);
        const startTime = performance.now();
        const socket = protocols === undefined ? new NativeWebSocket(url) : new NativeWebSocket(url, protocols);
        let connectEnded = false;

        const endConnectSpan = (status: 'error' | 'opened') => {
          if (connectEnded) return;
          connectEnded = true;
          if (status === 'error') {
            connectSpan.setStatus({ code: SpanStatusCode.ERROR, message: 'websocket connect failed' });
          }
          connectSpan.setAttribute('websocket.connect.duration_ms', performance.now() - startTime);
          connectSpan.end();
        };

        socket.addEventListener('open', () => endConnectSpan('opened'));

        socket.addEventListener('message', event => {
          messageCounter.add(1, { ...metricAttributes, 'websocket.direction': 'in' });
          bytesCounter.add(getMessageByteLength(event.data), {
            ...metricAttributes,
            'websocket.direction': 'in',
          });
        });

        socket.addEventListener('error', () => {
          errorCounter.add(1, metricAttributes);
          endConnectSpan('error');
          context.emitLog({
            severityNumber: SeverityNumber.ERROR,
            severityText: 'ERROR',
            body: 'websocket.error',
            attributes: spanAttributes,
          });
        });

        socket.addEventListener('close', event => {
          endConnectSpan('opened');
          context.emitLog({
            severityNumber: SeverityNumber.INFO,
            severityText: 'INFO',
            body: 'websocket.close',
            attributes: {
              ...spanAttributes,
              'websocket.close.code': event.code,
              'websocket.close.reason': event.reason,
              'websocket.close.was_clean': event.wasClean,
            },
          });
        });

        // 计量发送方向（无法拦截 send 的回调，所以包一层 send 方法）
        const originalSend = socket.send.bind(socket);
        socket.send = (data: ArrayBufferLike | ArrayBufferView | Blob | string) => {
          messageCounter.add(1, { ...metricAttributes, 'websocket.direction': 'out' });
          bytesCounter.add(getMessageByteLength(data), {
            ...metricAttributes,
            'websocket.direction': 'out',
          });
          return originalSend(data);
        };

        return socket;
      } as unknown as typeof WebSocket;

      // 复制原型与静态常量（CONNECTING / OPEN / CLOSING / CLOSED 等），避免业务侧 WebSocket.OPEN 失效
      PatchedWebSocket.prototype = NativeWebSocket.prototype;
      Object.assign(PatchedWebSocket, NativeWebSocket);

      window.WebSocket = PatchedWebSocket;
    },
    shutdown() {
      if (originalWebSocket && typeof window !== 'undefined') {
        window.WebSocket = originalWebSocket;
      }
    },
  };
};
