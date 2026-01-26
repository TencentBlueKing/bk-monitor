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

import { random } from '@/common/util';
import { join } from '@/global/utils/path';
import store from '@/store';
import { FetchResponse } from './types';

const baseURL = window.AJAX_URL_PREFIX || '/api/v1';
const xsrfCookieName = 'bklog_csrftoken';
const xsrfHeaderName = 'X-CSRFToken';

/**
 * 获取Cookie
 * @param {String} name
 */
const getCookie = (name: string): string | null => {
  const reg = new RegExp(`(^|)${name}=([^;]*)(;|$)`);
  const data = document.cookie.match(reg);
  if (data) {
    return decodeURIComponent(data[2]);
  }
  return null;
};

/**
 * 构建请求配置（模拟 axios 拦截器逻辑）
 */
const buildRequestConfig = (
  url: string,
  params?: any,
  method: 'POST' | 'GET' | 'PUT' = 'POST',
  appendHeaders?: Record<string, string>,
  signal?: AbortSignal,
) => {
  // URL 处理（对应 axios 拦截器中的 URL 检查）
  // 如果URL是外部API（如 /api/bk-user-web），直接使用，不拼接 baseURL
  // 如果URL是相对路径，拼接 baseURL
  let fullUrl: string;
  if (url.startsWith('/api/bk-user-web')) {
    // 外部API，直接使用完整路径
    fullUrl = url;
  } else if (/^(https|http)?:\/\//.test(url)) {
    // 绝对URL，直接使用
    fullUrl = url;
  } else {
    // 相对路径，拼接 baseURL
    fullUrl = join(baseURL, url);
  }

  // 构建 headers（对应 axios 配置）
  const headers: Record<string, string> = {
    'X-Requested-With': 'XMLHttpRequest',
    'Content-Type': 'application/json',
  };

  if (store.state.userMeta?.bk_tenant_id) {
    headers['X-Bk-Tenant-Id'] = store.state.userMeta?.bk_tenant_id;
  }

  // CSRF Token（对应 axios xsrfCookieName 和 xsrfHeaderName）
  const csrfToken = getCookie(xsrfCookieName);
  if (csrfToken) {
    headers[xsrfHeaderName] = csrfToken;
  }

  // 外部版后端需要读取header里的 spaceUid（对应 axios 拦截器）
  if (window.IS_EXTERNAL && JSON.parse(window.IS_EXTERNAL as string) && store.state.spaceUid) {
    headers['X-Bk-Space-Uid'] = store.state.spaceUid;
  }

  // 监控上层并没有使用 OT 这里直接自己生成traceparent id（对应 axios 拦截器）
  const traceparent = `00-${random(32, 'abcdef0123456789')}-${random(16, 'abcdef0123456789')}-01`;
  headers.Traceparent = traceparent;

  // 构建 fetch 配置（对应 axios withCredentials: true）
  const fetchConfig: RequestInit = {
    method,
    headers: { ...headers, ...appendHeaders },
    credentials: 'include', // 对应 axios withCredentials: true
    body: params ? JSON.stringify(params) : undefined,
    signal, // 支持 AbortController
  };

  return { url: fullUrl, config: fetchConfig };
};

/**
 * @description 请求 API
 * @param args 请求参数
 * @param args.url 请求 URL
 * @param args.params 请求参数
 * @param args.method 请求方法
 * @param args.headers 请求头
 * @param args.signal AbortSignal 用于取消请求
 * @returns {Promise<Response>}
 */
export const request = (args: {
  url: string;
  params?: any;
  method?: 'POST' | 'GET' | 'PUT';
  headers?: Record<string, string>;
  signal?: AbortSignal;
}) => {
  const { url, params = {}, method = 'POST', headers = {}, signal } = args;
  const { url: fullUrl, config } = buildRequestConfig(url, params, method, headers, signal);
  return fetch(fullUrl, config);
};

/**
 * @description 请求 API
 * @param url string
 * @param params any
 * @param method 'POST' | 'GET' | 'PUT'
 * @returns {Promise<FetchResponse<T>>}
 */
export const requestJson = <T = any>(args: Parameters<typeof request>[0]): Promise<FetchResponse<T>> => {
  return request(args)
    .then(response => response.json())
    .then(data => data as FetchResponse<T>);
};

/**
 * @description 请求 API
 * @param url string
 * @param params any
 * @param method 'POST' | 'GET' | 'PUT'
 * @returns {Promise<string>}
 */
export const requestText = (args: Parameters<typeof request>[0]): Promise<string> => {
  return request(args)
    .then(response => response.text())
    .then(data => data);
};

/**
 * @description 请求 API，返回 Blob 响应（用于处理长整型精度问题）
 * @param args 请求参数
 * @returns {Promise<Response>} 返回 Response 对象，可以通过 response.blob() 获取 Blob
 */
export const requestBlob = (args: Parameters<typeof request>[0]): Promise<Response> => {
  const { headers = {} } = args;
  // 确保 Accept header 包含 application/json，以便后端返回正确的 Content-Type
  const blobHeaders = {
    Accept: 'application/json',
    ...headers,
  };
  return request({ ...args, headers: blobHeaders });
};
