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
interface IRouterParams {
  name: string;
  params: Record<string, unknown>;
  query: Record<string, unknown>;
}
export function monitorLink(routeParams: IRouterParams) {
  if (routeParams.name === 'retrieve') {
    const params = {
      ...window.mainComponent.$router.query,
      ...window.mainComponent.$router.params,
      ...routeParams,
      name: window.__IS_MONITOR_TRACE__ ? 'trace-retrieval' : 'apm-others',
      path: window.__IS_MONITOR_TRACE__ ? '/trace/home' : '/apm/service',
    };
    const url = window.mainComponent.$router.resolve(params).href;
    return url;
  }
  const url = window.mainComponent.$router.resolve(routeParams).href;
  const link = `${window.bk_log_search_url}${url}`;
  return link;
}
