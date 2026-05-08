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

import { SeverityNumber } from '@opentelemetry/api-logs';

import { shouldIgnoreUrl } from '../core/url';

import type { BkOTHttpBodyConfig, BkOTHttpBodyRedactPayload } from '../core/config';
import type { BkOTPlugin, BkOTRuntimeContext } from '../core/plugin';
import type { Attributes } from '@opentelemetry/api';

interface BodySnapshot {
  body: string;
  contentType?: string;
  truncated: boolean;
}

interface ReportHttpBodyOptions {
  context: BkOTRuntimeContext;
  duration: number;
  error?: unknown;
  method: string;
  request?: BodySnapshot;
  response?: BodySnapshot;
  status?: number;
  url: string;
}

const HTTP_BODY_MAX_SIZE = 10 * 1024;

type HttpBodyInput = BodyInit | Document | null | undefined;

const truncateBody = (body: string, maxBodySize: number): Pick<BodySnapshot, 'body' | 'truncated'> => {
  if (body.length <= maxBodySize) {
    return {
      body,
      truncated: false,
    };
  }
  return {
    body: body.slice(0, maxBodySize),
    truncated: true,
  };
};

const getHeaderValue = (headers: HeadersInit | undefined, key: string) => {
  if (!headers) {
    return undefined;
  }
  if (headers instanceof Headers) {
    return headers.get(key) || undefined;
  }
  const normalizedKey = key.toLowerCase();
  if (Array.isArray(headers)) {
    return headers.find(([itemKey]) => itemKey.toLowerCase() === normalizedKey)?.[1];
  }
  const matchedKey = Object.keys(headers).find(item => item.toLowerCase() === normalizedKey);
  return matchedKey ? headers[matchedKey] : undefined;
};

const stringifyFormData = (body: FormData) => {
  const entries: Record<string, string> = {};
  body.forEach((value, key) => {
    entries[key] =
      value instanceof File ? `[File name=${value.name} type=${value.type || 'unknown'} size=${value.size}]` : value;
  });
  return JSON.stringify(entries);
};

const stringifyBody = async (body: HttpBodyInput): Promise<string> => {
  if (body == null) {
    return '';
  }
  if (typeof body === 'string') {
    return body;
  }
  if (body instanceof URLSearchParams) {
    return body.toString();
  }
  if (body instanceof FormData) {
    return stringifyFormData(body);
  }
  if (body instanceof Blob) {
    return body.text();
  }
  if (body instanceof ArrayBuffer) {
    return new TextDecoder().decode(body);
  }
  if (ArrayBuffer.isView(body)) {
    return new TextDecoder().decode(body);
  }
  if (body instanceof Document) {
    return new XMLSerializer().serializeToString(body);
  }
  return String(body);
};

const createBodySnapshot = async (
  body: HttpBodyInput,
  maxBodySize: number,
  contentType?: string
): Promise<BodySnapshot | undefined> => {
  const rawBody = await stringifyBody(body);
  if (!rawBody) {
    return undefined;
  }
  return {
    ...truncateBody(rawBody, maxBodySize),
    contentType,
  };
};

const safeCreateBodySnapshot = async (body: HttpBodyInput, maxBodySize: number, contentType?: string) => {
  try {
    return await createBodySnapshot(body, maxBodySize, contentType);
  } catch {
    return undefined;
  }
};

const getFetchInputUrl = (input: RequestInfo | URL) => {
  if (input instanceof Request) {
    return input.url;
  }
  return String(input);
};

const getFetchMethod = (input: RequestInfo | URL, init?: RequestInit) => {
  if (init?.method) {
    return init.method;
  }
  if (input instanceof Request) {
    return input.method;
  }
  return 'GET';
};

const getFetchRequestBody = async (input: RequestInfo | URL, init: RequestInit | undefined, maxBodySize: number) => {
  if (init?.body) {
    return safeCreateBodySnapshot(
      init.body,
      maxBodySize,
      getHeaderValue(init.headers as Headers | undefined, 'content-type')
    );
  }
  if (input instanceof Request) {
    try {
      return safeCreateBodySnapshot(
        await input.clone().text(),
        maxBodySize,
        input.headers.get('content-type') || undefined
      );
    } catch {
      return undefined;
    }
  }
  return undefined;
};

const getResponseBody = async (response: Response, maxBodySize: number) => {
  try {
    const clonedResponse = response.clone();
    return safeCreateBodySnapshot(
      clonedResponse.body ? await clonedResponse.text() : '',
      maxBodySize,
      response.headers.get('content-type') || undefined
    );
  } catch {
    return undefined;
  }
};

const getXhrResponseBody = (xhr: XMLHttpRequest, maxBodySize: number): BodySnapshot | undefined => {
  if (xhr.responseType === '' || xhr.responseType === 'text') {
    return {
      ...truncateBody(xhr.responseText || '', maxBodySize),
      contentType: xhr.getResponseHeader('content-type') || undefined,
    };
  }
  if (xhr.responseType === 'json') {
    return {
      ...truncateBody(JSON.stringify(xhr.response), maxBodySize),
      contentType: xhr.getResponseHeader('content-type') || undefined,
    };
  }
  return undefined;
};

const redactBody = (
  config: Required<BkOTHttpBodyConfig>,
  payload: Omit<BkOTHttpBodyRedactPayload, 'body' | 'truncated'>,
  snapshot?: BodySnapshot
) => {
  if (!snapshot) {
    return undefined;
  }
  return config.redact({
    ...payload,
    body: snapshot.body,
    truncated: snapshot.truncated,
  });
};

const reportHttpBody = ({
  context,
  duration,
  error,
  method,
  request,
  response,
  status,
  url,
}: ReportHttpBodyOptions) => {
  const config = context.config.rum.httpBody;
  if (!config) {
    return;
  }

  const isError = Boolean(error) || (typeof status === 'number' && status >= 400);
  const normalizedMethod = method.toUpperCase();
  const requestBody = isError
    ? redactBody(
        config,
        {
          contentType: request?.contentType,
          method: normalizedMethod,
          status,
          type: 'request',
          url,
        },
        request
      )
    : undefined;
  const responseBody = isError
    ? redactBody(
        config,
        {
          contentType: response?.contentType,
          method: normalizedMethod,
          status,
          type: 'response',
          url,
        },
        response
      )
    : undefined;
  const attributes: Attributes = {
    ...context.config.getPageAttributes(),
    'http.duration': duration,
    'http.request.method': normalizedMethod,
    'url.full': context.config.redactUrl(url),
  };

  if (typeof status === 'number') {
    attributes['http.response.status_code'] = status;
  }
  if (requestBody != null) {
    attributes['http.request.body'] = requestBody;
  }
  if (responseBody != null) {
    attributes['http.response.body'] = responseBody;
  }
  if (isError) {
    attributes['bk.rum.http_body.request.truncated'] = request?.truncated ?? false;
    attributes['bk.rum.http_body.response.truncated'] = response?.truncated ?? false;
  }
  if (error instanceof Error) {
    attributes['exception.message'] = error.message;
    attributes['exception.type'] = error.name;
    attributes['exception.stacktrace'] = error.stack ?? '';
  }

  context.emitLog({
    severityNumber: isError ? SeverityNumber.ERROR : SeverityNumber.INFO,
    severityText: isError ? 'ERROR' : 'INFO',
    body: isError ? 'HTTP request completed with error' : 'HTTP request completed',
    attributes,
  });
};

export const createHttpBodyPlugin = (option: false | Required<BkOTHttpBodyConfig>): BkOTPlugin => {
  const teardownCallbacks: Array<() => void> = [];

  return {
    name: 'http-body',
    enabled: Boolean(option),
    init(context) {
      if (!option || typeof window === 'undefined') {
        return;
      }

      const maxBodySize = option.maxBodySize || HTTP_BODY_MAX_SIZE;
      const originalFetch = window.fetch;
      if (typeof originalFetch === 'function') {
        window.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
          const url = getFetchInputUrl(input);
          if (shouldIgnoreUrl(context.config, url)) {
            return originalFetch(input, init);
          }
          const method = getFetchMethod(input, init);
          const request = await getFetchRequestBody(input, init, maxBodySize);
          const startTime = performance.now();
          try {
            const response = await originalFetch(input, init);
            const duration = performance.now() - startTime;
            const responseBody = response.status >= 400 ? await getResponseBody(response, maxBodySize) : undefined;
            reportHttpBody({
              context,
              duration,
              method,
              request,
              response: responseBody,
              status: response.status,
              url,
            });
            return response;
          } catch (error) {
            reportHttpBody({
              context,
              duration: performance.now() - startTime,
              error,
              method,
              request,
              url,
            });
            throw error;
          }
        };
        teardownCallbacks.push(() => {
          window.fetch = originalFetch;
        });
      }

      const originalOpen = XMLHttpRequest.prototype.open;
      const originalSend = XMLHttpRequest.prototype.send;
      const originalSetRequestHeader = XMLHttpRequest.prototype.setRequestHeader;
      XMLHttpRequest.prototype.open = function open(
        this: XMLHttpRequest,
        method: string,
        url: string | URL,
        ...args: [async?: boolean, username?: null | string, password?: null | string]
      ) {
        this.__bkOtHttpBodyMeta__ = {
          method,
          startTime: performance.now(),
          url: String(url),
        };
        return originalOpen.call(this, method, url, ...args);
      };
      XMLHttpRequest.prototype.setRequestHeader = function setRequestHeader(
        this: XMLHttpRequest,
        name: string,
        value: string
      ) {
        this.__bkOtHttpBodyRequestHeaders__ = {
          ...(this.__bkOtHttpBodyRequestHeaders__ ?? {}),
          [name]: value,
        };
        return originalSetRequestHeader.call(this, name, value);
      };
      XMLHttpRequest.prototype.send = function send(
        this: XMLHttpRequest,
        body?: Document | null | XMLHttpRequestBodyInit
      ) {
        void safeCreateBodySnapshot(
          body,
          maxBodySize,
          getHeaderValue(this.__bkOtHttpBodyRequestHeaders__, 'content-type')
        ).then(request => {
          this.__bkOtHttpBodyRequest__ = request;
        });
        this.addEventListener('loadend', () => {
          const meta = this.__bkOtHttpBodyMeta__;
          if (!meta || shouldIgnoreUrl(context.config, meta.url)) {
            return;
          }
          const responseBody = this.status >= 400 ? getXhrResponseBody(this, maxBodySize) : undefined;
          reportHttpBody({
            context,
            duration: performance.now() - meta.startTime,
            method: meta.method,
            request: this.__bkOtHttpBodyRequest__,
            response: responseBody,
            status: this.status,
            url: meta.url,
          });
        });
        return originalSend.call(this, body);
      };
      teardownCallbacks.push(() => {
        XMLHttpRequest.prototype.open = originalOpen;
        XMLHttpRequest.prototype.send = originalSend;
        XMLHttpRequest.prototype.setRequestHeader = originalSetRequestHeader;
      });
    },
    shutdown() {
      while (teardownCallbacks.length) {
        teardownCallbacks.pop()?.();
      }
    },
  };
};

declare global {
  interface XMLHttpRequest {
    __bkOtHttpBodyRequest__?: BodySnapshot;
    __bkOtHttpBodyRequestHeaders__?: Record<string, string>;
    __bkOtHttpBodyMeta__?: {
      method: string;
      startTime: number;
      url: string;
    };
  }
}
