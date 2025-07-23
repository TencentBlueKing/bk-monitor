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
export type JsonpCallback<T> = (response: T) => void;

interface JsonpOptions<T> {
  data?: Record<string, number | string>;
  callback?: JsonpCallback<T>;
  onError?: (e: Event | string) => void;
}
/**
 *
 * @param url jsonp url
 * @param options jsonp options
 */
export function jsonp<T>(url: string, options: JsonpOptions<T>): void {
  if (!url) {
    throw new Error('JSONP URL is necessary');
  }

  const callbackName = `CALLBACK${Math.random().toString().substr(9, 18)}`;
  const scriptElement = document.createElement('script');
  scriptElement.setAttribute('type', 'text/javascript');
  const headElement = document.head;

  const handleResponse = (response: T) => {
    options.callback?.(response);
    cleanup();
  };

  const handleError = (e: Event | string) => {
    options.onError?.(e);
    cleanup();
  };

  const cleanup = () => {
    scriptElement.onerror = null;
    delete window[callbackName];
    scriptElement.remove();
  };

  scriptElement.onerror = handleError;
  window[callbackName] = handleResponse;

  const params = new URLSearchParams();
  if (options.data) {
    for (const key in options.data) {
      if (Object.hasOwn(options.data, key)) {
        params.append(key, String(options.data[key]));
      }
    }
    params.append('callback', callbackName);
  }

  const urlWithParams = new URL(url);
  urlWithParams.search = params.toString();

  scriptElement.src = urlWithParams.href;
  headElement.appendChild(scriptElement);
}

/**
 *
 * @param url jsonp url
 * @param options jsonp options
 * @returns Promise
 */
export function useJSONP<T>(url: string, options: JsonpOptions<T>): Promise<T> {
  return new Promise((resolve, reject) => {
    jsonp(url, {
      ...options,
      callback: (response: T) => {
        resolve(response);
      },
      onError: (e: Event | string) => {
        reject(e);
      },
    });
  });
}
