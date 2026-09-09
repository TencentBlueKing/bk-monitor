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

/**
 * Isolated Webpack Dev settings for local Playwright e2e.
 * Loaded only when BKLOG_E2E_DEV=1. Does not read local.settings.js or .cookie.
 */
const context = ['/apm', '/rest', '/fta', '/api', '/weixin', '/version_log', '/calendars', '/alert', '/query-api'];
const changeOrigin = true;
const secure = false;
const port = 8011;
const devProxyUrl = 'https://bklog.bkop.woa.com';
const loginHost = `${devProxyUrl}/login`;
const host = `appdev.${devProxyUrl.match(/\.([^.]+)\.com\/?/)[1]}.com`;

function inheritRequestCookie(proxyReq, req) {
  const incoming = req.headers.cookie;
  if (incoming) {
    proxyReq.setHeader('Cookie', incoming);
    return;
  }
  proxyReq.removeHeader('Cookie');
}

const proxy = [{
  context,
  changeOrigin,
  secure,
  target: devProxyUrl,
  headers: {
    host: devProxyUrl.replace(/https?:\/\//i, ''),
    referer: devProxyUrl,
  },
  onProxyReq: inheritRequestCookie,
}];

module.exports = {
  port,
  devProxyUrl,
  loginHost,
  host,
  proxy,
};
